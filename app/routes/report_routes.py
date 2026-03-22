import os
import json
import csv
from io import StringIO
from datetime import date, timedelta
from calendar import monthrange
from collections import defaultdict

from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify, Response, current_app
from flask.views import MethodView
from flask_login import login_required, current_user

from sqlalchemy.orm import selectinload
from sqlalchemy import func, case, extract, and_

from app.modules.auth.models import User, Role
from app.modules.store.models import Location, Category
from app.modules.daily_ops.models import BusinessDay, DailySettlement
from app.modules.pos.models import Transaction, TransactionItem
from app.modules.system.models import SystemSetting
from app.modules.report.forms import ReportQueryForm
from app.modules.daily_ops.forms import SettlementForm

from app.core.extensions import db, login_manager, csrf
from app.core.decorators import admin_required
from app.services.settlement_service import SettlementService, FINANCE_ITEMS, SALES_ITEMS

from app.services.pdf_service import PDFGeneratorService

bp = Blueprint('report', __name__, url_prefix='/report')

LOCATION_ORDER = ["本舖", "瘋衣舍", "特賣會 1", "特賣會 2", "其他"]
DENOMINATIONS = [1000, 500, 200, 100, 50, 10, 5, 1]

# ==========================================
# Helpers
# ==========================================
def get_date_range_from_period(time_unit, year=None, month=None, quarter=None, period_str=None):
    try:
        if time_unit == 'month':
            if not period_str: return None, None
            year, month = map(int, period_str.split('-'))
            start_date = date(year, month, 1)
            end_date = date(year, month, monthrange(year, month)[1])
        elif time_unit == 'quarter':
            if not year or not quarter: return None, None
            year, quarter = int(year), int(quarter)
            start_month = (quarter - 1) * 3 + 1
            end_month = start_month + 2
            start_date = date(year, start_month, 1)
            end_date = date(year, end_month, monthrange(year, end_month)[1])
        elif time_unit == 'year':
            if not year: return None, None
            year = int(year)
            start_date = date(year, 1, 1)
            end_date = date(year, 12, 31)
        else:
            return None, None
        return start_date, end_date
    except (ValueError, TypeError, AttributeError):
        return None, None

# ==========================================
# Base View
# ==========================================

from functools import wraps
from flask import abort

def require_permission(perm):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.can(perm):
                from flask import flash, redirect, url_for
                flash(f"存取遭拒：您不具備報表模組的進階權限。 ({perm})", "danger")
                return redirect(url_for('main.index'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

class ReportQueryAuthorizedView(MethodView):
    decorators = [login_required, require_permission('report_view_daily')]

class ReportConsolidatedAuthorizedView(MethodView):
    decorators = [login_required, require_permission('report_consolidated')]
# ==========================================
# Views
# ==========================================
class ReportQueryView(ReportQueryAuthorizedView):
    def get(self):
        form = ReportQueryForm()
        all_categories = Category.query.all()
        form.location_id.choices = [('all', '所有據點')] + [(str(l.id), l.name) for l in Location.query.order_by(Location.id).all()]
        
        results = []
        grand_total = None
        chart_data = None
        total_revenue = 0
        report_type = request.args.get('report_type')
        form.report_type.data = report_type

        if report_type:
            form.process(request.args)
            location_id = request.args.get('location_id', 'all')
            
            if report_type == 'daily_settlement_query':
                try:
                    start_date = date.fromisoformat(request.args.get('start_date', ''))
                    ed = request.args.get('end_date')
                    end_date = date.fromisoformat(ed) if ed else date.today()
                except ValueError:
                    start_date = date.today()
                    end_date = date.today()
                    flash('無效的日期格式，已自動選取今日。', 'warning')
                    form.start_date.data = start_date
                    form.end_date.data = end_date
                    return render_template('report/query.html', form=form, report_type=report_type, results=results, all_categories=all_categories)
                
                status_filter = request.args.get('status', 'all')
                locations = Location.query.order_by(Location.id).all()
                results = []
                for loc in locations:
                    if location_id != 'all' and str(loc.id) != location_id:
                        continue
                    current_date = start_date
                    while current_date <= end_date:
                        business_day = BusinessDay.query.filter(and_(BusinessDay.date == current_date, BusinessDay.location_id == loc.id)).first()
                        status_info = None
                        if business_day:
                            if business_day.status == 'CLOSED':
                                status_info = {'status_text': '已日結', 'badge_class': 'bg-primary', 'button_text': '查詢日結報表', 'button_url': url_for('cashier.daily_report', location_slug=loc.slug, date=current_date.isoformat()), 'button_class': 'btn-primary'}
                            elif business_day.status == 'PENDING_REPORT':
                                status_info = {'status_text': '待確認報表', 'badge_class': 'bg-warning text-dark', 'button_text': '確認報表', 'button_url': url_for('cashier.daily_report', location_slug=loc.slug, date=current_date.isoformat()), 'button_class': 'btn-warning'}
                            elif business_day.status == 'OPEN':
                                status_info = {'status_text': '營業中', 'badge_class': 'bg-success', 'button_text': '強制日結盤點', 'button_url': url_for('admin.force_close_day', business_day_id=business_day.id), 'button_class': 'btn-danger'}
                        else:
                            status_info = {'status_text': '沒有營業', 'badge_class': 'bg-secondary', 'button_text': '日結盤點', 'button_url': url_for('admin.new_force_close_day', location_id=loc.id, date=current_date.isoformat()), 'button_class': 'btn-danger'}
                        
                        is_filtered_out = False
                        if status_filter != 'all':
                            if status_filter == 'open' and business_day and business_day.status != 'OPEN': is_filtered_out = True
                            if status_filter == 'pending_report' and (not business_day or business_day.status != 'PENDING_REPORT'): is_filtered_out = True
                            if status_filter == 'closed' and (not business_day or business_day.status != 'CLOSED'): is_filtered_out = True
                            if status_filter == 'no_data' and business_day: is_filtered_out = True
                        
                        if not is_filtered_out:
                            results.append({'location': loc, 'date': current_date, 'status_info': status_info})
                        current_date += timedelta(days=1)
                
                return render_template('report/query.html', form=form, results=results, report_type=report_type, all_categories=all_categories)

            if report_type != 'periodic_performance':
                start_date_str = request.args.get('start_date')
                if not start_date_str:
                    start_date = end_date = date.today()
                    flash('查詢日期為必填欄位，已自動選取今日。', 'info')
                    form.start_date.data = start_date
                    form.end_date.data = end_date
                else:
                    try:
                        start_date = date.fromisoformat(start_date_str)
                        ed = request.args.get('end_date')
                        end_date = date.fromisoformat(ed) if ed else start_date
                    except ValueError:
                        start_date = end_date = date.today()
                        flash('無效的日期格式，已自動選取今日。', 'warning')
                        form.start_date.data = start_date
                        form.end_date.data = end_date
            else:
                time_unit = request.args.get('time_unit')
                start_date_a, end_date_a = get_date_range_from_period(time_unit, year=request.args.get('year_a'), quarter=request.args.get('quarter_a'), period_str=request.args.get('period_a'))
                start_date_b, end_date_b = get_date_range_from_period(time_unit, year=request.args.get('year_b'), quarter=request.args.get('quarter_b'), period_str=request.args.get('period_b'))
                if not all([start_date_a, end_date_a, start_date_b, end_date_b]):
                    flash('週期性報表的時間參數不完整或格式錯誤，請重新選擇。', 'warning')
                    return render_template('report/query.html', form=form, all_categories=all_categories)

            if report_type != 'periodic_performance':
                query_base = db.session.query(BusinessDay).options(db.joinedload(BusinessDay.location)).filter(BusinessDay.date.between(start_date, end_date))
                if location_id != 'all': query_base = query_base.filter(BusinessDay.location_id == location_id)

            if report_type == 'daily_summary':
                results = query_base.order_by(BusinessDay.date.desc(), BusinessDay.location_id).all()
                if results:
                    chart_labels = sorted(list(set(r.date.strftime('%Y-%m-%d') for r in results)))
                    locations = sorted(list(set(r.location.name for r in results)))
                    datasets = []
                    for loc_name in locations:
                        data = [sum(r.total_sales or 0 for r in results if r.date.strftime('%Y-%m-%d') == label_date and r.location.name == loc_name) for label_date in chart_labels]
                        datasets.append({'label': loc_name, 'data': data})
                    chart_data = {'labels': chart_labels, 'datasets': datasets}

            elif report_type == 'transaction_log':
                business_day_ids = [b.id for b in query_base.all()]
                results = db.session.query(Transaction).join(BusinessDay).options(
                    selectinload(Transaction.items).selectinload(TransactionItem.category),
                    db.joinedload(Transaction.business_day).joinedload(BusinessDay.location)
                ).filter(Transaction.business_day_id.in_(business_day_ids)).order_by(Transaction.timestamp).all()

            elif report_type in ['daily_cash_summary', 'daily_cash_check']:
                results = query_base.order_by(BusinessDay.date.desc(), BusinessDay.location_id).all()
                if results:
                    for r in results:
                        other_incomes = db.session.query(Category.name, func.sum(TransactionItem.price)) \
                            .join(TransactionItem.transaction).join(Transaction.business_day).join(TransactionItem.category) \
                            .filter(BusinessDay.id == r.id, Category.category_type == 'other_income') \
                            .group_by(Category.name).all()
                        r.donation_total = r.other_total = 0
                        for name, total in other_incomes:
                            if name == '捐款': r.donation_total = total or 0
                            else: r.other_total += total or 0
                    
                    grand_total_dict = {
                        'opening_cash': sum(r.opening_cash or 0 for r in results),
                        'total_sales': sum(r.total_sales or 0 for r in results),
                        'expected_cash': sum(r.expected_cash or 0 for r in results),
                        'closing_cash': sum(r.closing_cash or 0 for r in results),
                        'cash_diff': sum(r.cash_diff or 0 for r in results),
                        'donation_total': sum(r.donation_total or 0 for r in results),
                        'other_total': sum(r.other_total or 0 for r in results),
                        'location_notes': ""
                    }
                    grand_total_dict['other_cash'] = grand_total_dict['donation_total'] + grand_total_dict['other_total']
                    class GrandTotal:
                        def __init__(self, **entries): self.__dict__.update(entries)
                    grand_total = GrandTotal(**grand_total_dict)
                    
                    sales_by_location = defaultdict(float)
                    for r in results: sales_by_location[r.location.name] += r.total_sales or 0
                    chart_data = {'labels': list(sales_by_location.keys()), 'datasets': [{'label': '手帳營收', 'data': list(sales_by_location.values())}]}
            
            elif report_type == 'combined_summary_final':
                check_results = []
                all_settlements = DailySettlement.query.filter(DailySettlement.date.between(start_date - timedelta(days=1), end_date)).all()
                all_business_days = BusinessDay.query.filter(BusinessDay.date.between(start_date, end_date)).all()
                settlements_by_date = {s.date: s for s in all_settlements}
                business_days_by_date = defaultdict(list)
                for bd in all_business_days: business_days_by_date[bd.date].append(bd)
                
                current_date = start_date
                while current_date <= end_date:
                    previous_date = current_date - timedelta(days=1)
                    yesterday_settlement = settlements_by_date.get(previous_date)
                    today_reports = business_days_by_date.get(current_date, [])
                    total_next_day_cash_from_yesterday = yesterday_settlement.total_next_day_opening_cash if yesterday_settlement else 0
                    total_opening_cash_today = sum(r.opening_cash or 0 for r in today_reports)
                    cash_check_diff = total_opening_cash_today - total_next_day_cash_from_yesterday
                    if today_reports or yesterday_settlement:
                        check_results.append({
                            'date': current_date, 'cash_check_diff': cash_check_diff,
                            'yesterday_total': total_next_day_cash_from_yesterday, 'today_total': total_opening_cash_today
                        })
                    current_date += timedelta(days=1)
                results = check_results

            elif report_type == 'product_mix':
                query = db.session.query(Category.name.label('category_name'), func.sum(case((TransactionItem.price > 0, TransactionItem.price), else_=0)).label('total_sales'), func.count(case((TransactionItem.price > 0, TransactionItem.id), else_=None)).label('items_sold')) \
                    .join(TransactionItem.transaction).join(Transaction.business_day).join(TransactionItem.category) \
                    .filter(BusinessDay.date.between(start_date, end_date), Category.category_type == 'product')
                if location_id != 'all': query = query.filter(BusinessDay.location_id == location_id)
                results = query.group_by(Category.name).order_by(func.sum(TransactionItem.price).desc()).all()
                total_revenue = sum(r.total_sales for r in results) if results else 0
                chart_data = {'labels': [r.category_name for r in results], 'datasets': [{'label': '銷售總額', 'data': [r.total_sales for r in results]}]}

            elif report_type == 'sales_trend':
                query = db.session.query(BusinessDay.date, func.sum(BusinessDay.total_sales).label('total_sales'), func.sum(BusinessDay.total_transactions).label('total_transactions')).filter(BusinessDay.date.between(start_date, end_date))
                if location_id != 'all': query = query.filter(BusinessDay.location_id == location_id)
                results = query.group_by(BusinessDay.date).order_by(BusinessDay.date).all()
                chart_data = {
                    'labels': [r.date.strftime('%Y-%m-%d') for r in results],
                    'datasets': [{'label': '總銷售額', 'data': [r.total_sales for r in results], 'borderColor': 'rgb(75, 192, 192)', 'tension': 0.1, 'yAxisID': 'y'}, {'label': '總交易筆數', 'data': [r.total_transactions for r in results], 'borderColor': 'rgb(255, 99, 132)', 'tension': 0.1, 'yAxisID': 'y1'}]
                }

            elif report_type == 'peak_hours':
                query = db.session.query(func.strftime('%H', Transaction.timestamp).label('hour'), func.count(Transaction.id).label('transactions'), func.sum(Transaction.amount).label('total_sales')).join(BusinessDay).filter(BusinessDay.date.between(start_date, end_date))
                if location_id != 'all': query = query.filter(BusinessDay.location_id == location_id)
                results = query.group_by('hour').order_by('hour').all()
                chart_data = {
                    'labels': [f"{r.hour}:00 - {int(r.hour)+1}:00" for r in results],
                    'datasets': [{'label': '交易筆數', 'data': [r.transactions for r in results]}, {'label': '銷售總額', 'data': [r.total_sales for r in results]}]
                }

            elif report_type == 'periodic_performance':
                def get_period_data(start, end, unit):
                    t_expr = {
                        'year': [extract('year', BusinessDay.date)],
                        'quarter': [extract('year', BusinessDay.date), case((extract('month', BusinessDay.date) <= 3, 1), (extract('month', BusinessDay.date) <= 6, 2), (extract('month', BusinessDay.date) <= 9, 3), else_=4)],
                        'month': [extract('year', BusinessDay.date), extract('month', BusinessDay.date)]
                    }
                    query = db.session.query(*t_expr[unit], func.sum(BusinessDay.total_sales).label('total_sales'), func.sum(BusinessDay.total_transactions).label('total_transactions')).filter(BusinessDay.date.between(start, end))
                    if location_id != 'all': query = query.filter(BusinessDay.location_id == location_id)
                    return query.group_by(*t_expr[unit]).order_by(*t_expr[unit]).all()

                data_a = get_period_data(start_date_a, end_date_a, time_unit)
                data_b = get_period_data(start_date_b, end_date_b, time_unit)
                dict_a = {tuple(row[:-2]): row[-2:] for row in data_a}
                dict_b = {tuple(row[:-2]): row[-2:] for row in data_b}
                all_keys = sorted(list(set(dict_a.keys()) | set(dict_b.keys())))
                results = []
                for key in all_keys:
                    sales_a, trans_a = dict_a.get(key, (0, 0))
                    sales_b, trans_b = dict_b.get(key, (0, 0))
                    sales_diff = (sales_b or 0) - (sales_a or 0)
                    sales_perc = (sales_diff / sales_a * 100) if sales_a else float('inf')
                    label = ""
                    if time_unit == 'year': label = str(key[0])
                    elif time_unit == 'quarter': label = f"{key[0]}-Q{key[1]}"
                    elif time_unit == 'month': label = f"{key[0]}-{key[1]:02d}"
                    results.append({'label': label, 'sales_a': sales_a or 0, 'trans_a': trans_a or 0, 'sales_b': sales_b or 0, 'trans_b': trans_b or 0, 'sales_diff': sales_diff, 'sales_perc': sales_perc})
                chart_data = {'labels': [r['label'] for r in results], 'datasets': [{'label': '期間 A', 'data': [r['sales_a'] for r in results]}, {'label': '期間 B', 'data': [r['sales_b'] for r in results]}]}
                
        return render_template('report/query.html', form=form, results=results, report_type=report_type, grand_total=grand_total, chart_data=json.dumps(chart_data) if chart_data else None, total_revenue=total_revenue, denominations=DENOMINATIONS, all_categories=[{'id': c.id, 'name': c.name, 'category_type': c.category_type} for c in all_categories])


class SaveDailySummaryDataView(ReportQueryAuthorizedView):
    decorators = [login_required, admin_required, csrf.exempt]
    def post(self):
        try:
            for row_data in request.get_json():
                bd = BusinessDay.query.get(row_data.get('id'))
                if not bd: continue
                bd.opening_cash = float(row_data.get('opening_cash', bd.opening_cash))
                bd.expected_cash = (bd.opening_cash or 0) + (bd.total_sales or 0)
                bd.cash_diff = (bd.closing_cash or 0) - (bd.expected_cash or 0)
            db.session.commit()
            return jsonify({'success': True, 'message': '每日摘要數據已成功更新。'})
        except Exception as e:
            db.session.rollback()
            return jsonify({'success': False, 'message': str(e)}), 500

class SaveCashCheckDataView(ReportQueryAuthorizedView):
    decorators = [login_required, admin_required, csrf.exempt]
    def post(self):
        try:
            for row_data in request.get_json():
                bd = BusinessDay.query.get(row_data.get('id'))
                if not bd: continue
                cb_raw = row_data.get('cash_breakdown')
                if isinstance(cb_raw, dict):
                    cb_dict = {k: int(v) for k, v in cb_raw.items()}
                    bd.cash_breakdown = json.dumps(cb_dict)
                    bd.closing_cash = float(sum(int(d) * c for d, c in cb_dict.items()))
                bd.expected_cash = (bd.opening_cash or 0) + (bd.total_sales or 0)
                bd.cash_diff = (bd.closing_cash or 0) - (bd.expected_cash or 0)
            db.session.commit()
            return jsonify({'success': True, 'message': '報表數據已成功儲存！'})
        except Exception as e:
            db.session.rollback()
            return jsonify({'success': False, 'message': f'更新失敗: {str(e)}'}), 500

class SaveTransactionLogDataView(ReportQueryAuthorizedView):
    decorators = [login_required, admin_required, csrf.exempt]
    def post(self):
        try:
            for t_data in request.get_json():
                tx = Transaction.query.get(t_data.get('id'))
                if not tx: continue
                tx.cash_received = float(t_data.get('cash_received', tx.cash_received))
                for item_data in t_data.get('items', []):
                    item = TransactionItem.query.get(item_data.get('id'))
                    if item:
                        item.price = float(item_data.get('price', item.price))
                        item.category_id = item_data.get('category_id', item.category_id)
                tx.amount = sum(item.price for item in tx.items)
                tx.change_given = (tx.cash_received or 0) - (tx.amount or 0)
                bd = tx.business_day
                if bd:
                    bd.total_sales = sum(t.amount or 0 for t in BusinessDay.query.get(bd.id).transactions)
                    bd.expected_cash = (bd.opening_cash or 0) + (bd.total_sales or 0)
                    bd.cash_diff = (bd.closing_cash or 0) - (bd.expected_cash or 0)
            db.session.commit()
            return jsonify({'success': True, 'message': '交易細節數據已成功更新。'})
        except Exception as e:
            db.session.rollback()
            return jsonify({'success': False, 'message': str(e)}), 500

class SaveDailyCashSummaryDataView(ReportQueryAuthorizedView):
    decorators = [login_required, admin_required, csrf.exempt]
    def post(self):
        flash('錯誤：捐款與其他收入為累計欄位，無法手動修改。', 'danger')
        return jsonify({'success': False, 'message': '捐款與其他收入為累計欄位，無法手動修改。'}), 400

class ExportCSVView(ReportQueryAuthorizedView):
    def get(self):
        report_type = request.args.get('report_type')
        location_id = request.args.get('location_id')
        
        si = StringIO()
        cw = csv.writer(si)
        header = []
        results_to_write = []

        if report_type != 'periodic_performance':
            start_date = date.fromisoformat(request.args.get('start_date'))
            end_date_str = request.args.get('end_date')
            end_date = date.fromisoformat(end_date_str) if end_date_str else start_date
        else:
            time_unit = request.args.get('time_unit')
            start_date_a, end_date_a = get_date_range_from_period(time_unit, period_str=request.args.get('period_a'), year=request.args.get('year_a'), quarter=request.args.get('quarter_a'))
            start_date_b, end_date_b = get_date_range_from_period(time_unit, period_str=request.args.get('period_b'), year=request.args.get('year_b'), quarter=request.args.get('quarter_b'))
            if not all([start_date_a, end_date_a, start_date_b, end_date_b]):
                flash('無法匯出：週期性報表的時間參數不完整。', 'warning')
                return redirect(url_for('report.query'))

        if report_type == 'daily_summary':
            header = ['日期', '據點', '開店現金', '手帳營收', '其他現金', '應有現金', '實有現金', '溢短收', '交易筆數', '銷售件數']
            query = db.session.query(BusinessDay).filter(BusinessDay.date.between(start_date, end_date))
            if location_id != 'all': query = query.filter(BusinessDay.location_id == location_id)
            for r in query.order_by(BusinessDay.date.desc(), BusinessDay.location_id).all():
                other_incomes = db.session.query(Category.name, func.sum(TransactionItem.price)) \
                    .join(TransactionItem.transaction).join(Transaction.business_day).join(TransactionItem.category) \
                    .filter(BusinessDay.id == r.id, Category.category_type == 'other_income').group_by(Category.name).all()
                other_tot = sum(tot for name, tot in other_incomes if tot)
                results_to_write.append([r.date.strftime('%Y-%m-%d'), r.location.name, r.opening_cash, r.total_sales, other_tot, r.expected_cash, r.closing_cash, r.cash_diff, r.total_transactions, r.total_items])

        elif report_type == 'daily_cash_summary':
            header = ['日期', '據點', '開店現金', '手帳營收', '其他現金', '應有現金', '實有現金', '溢短收', '交易筆數', '銷售件數']
            query = db.session.query(BusinessDay).filter(BusinessDay.date.between(start_date, end_date))
            if location_id != 'all': query = query.filter(BusinessDay.location_id == location_id)
            for r in query.order_by(BusinessDay.date, BusinessDay.location_id).all():
                other_incomes = db.session.query(Category.name, func.sum(TransactionItem.price)) \
                    .join(TransactionItem.transaction).join(Transaction.business_day).join(TransactionItem.category) \
                    .filter(BusinessDay.id == r.id, Category.category_type == 'other_income').group_by(Category.name).all()
                other_tot = sum(tot for name, tot in other_incomes if tot)
                results_to_write.append([r.date.strftime('%Y-%m-%d'), r.location.name, r.opening_cash, r.total_sales, other_tot, r.expected_cash, r.closing_cash, r.cash_diff, r.total_transactions, r.total_items])

        elif report_type == 'daily_cash_check':
            header = ['日期', '據點', '總計'] + [str(d) for d in DENOMINATIONS]
            query = db.session.query(BusinessDay).filter(BusinessDay.date.between(start_date, end_date))
            if location_id != 'all': query = query.filter(BusinessDay.location_id == location_id)
            for r in query.order_by(BusinessDay.date, BusinessDay.location_id).all():
                cb = json.loads(r.cash_breakdown) if r.cash_breakdown else {}
                row = [r.date.strftime('%Y-%m-%d'), r.location.name, r.closing_cash or 0] + [cb.get(str(d), 0) for d in DENOMINATIONS]
                results_to_write.append(row)

        elif report_type == 'transaction_log':
            header = ['時間', '據點', '項目/折扣', '類型', '單價/折扣額', '收到現金', '交易總額', '找零']
            qb = db.session.query(BusinessDay).filter(BusinessDay.date.between(start_date, end_date))
            if location_id != 'all': qb = qb.filter(BusinessDay.location_id == location_id)
            bd_ids = [b.id for b in qb.all()]
            for trans in db.session.query(Transaction).filter(Transaction.business_day_id.in_(bd_ids)).order_by(Transaction.timestamp).all():
                for item in trans.items:
                    results_to_write.append([trans.timestamp.strftime('%Y-%m-%d %H:%M:%S'), trans.business_day.location.name, item.category.name if item.category else '手動輸入', '商品' if item.price > 0 else '折扣', item.price, trans.cash_received, trans.amount, trans.change_given])

        elif report_type == 'product_mix':
            header = ['類別名稱', '銷售數量', '銷售總額']
            q = db.session.query(Category.name, func.count(case((TransactionItem.price > 0, TransactionItem.id), else_=None)), func.sum(case((TransactionItem.price > 0, TransactionItem.price), else_=0))) \
                .join(TransactionItem.transaction).join(Transaction.business_day).join(TransactionItem.category).filter(BusinessDay.date.between(start_date, end_date), Category.category_type == 'product')
            if location_id != 'all': q = q.filter(BusinessDay.location_id == location_id)
            for r in q.group_by(Category.name).order_by(func.sum(TransactionItem.price).desc()).all():
                results_to_write.append([r[0], r[1], r[2]])

        elif report_type == 'sales_trend':
            header = ['日期', '總銷售額', '總交易筆數']
            q = db.session.query(BusinessDay.date, func.sum(BusinessDay.total_sales), func.sum(BusinessDay.total_transactions)).filter(BusinessDay.date.between(start_date, end_date))
            if location_id != 'all': q = q.filter(BusinessDay.location_id == location_id)
            for r in q.group_by(BusinessDay.date).order_by(BusinessDay.date).all():
                results_to_write.append([r[0].strftime('%Y-%m-%d'), r[1], r[2]])

        elif report_type == 'peak_hours':
            header = ['時段', '交易筆數', '銷售總額']
            q = db.session.query(func.strftime('%H', Transaction.timestamp), func.count(Transaction.id), func.sum(Transaction.amount)).join(BusinessDay).filter(BusinessDay.date.between(start_date, end_date))
            if location_id != 'all': q = q.filter(BusinessDay.location_id == location_id)
            for r in q.group_by(func.strftime('%H', Transaction.timestamp)).order_by(func.strftime('%H', Transaction.timestamp)).all():
                results_to_write.append([f"{r[0]}:00 - {int(r[0])+1}:00", r[1], r[2]])

        elif report_type == 'daily_settlement_query':
            header = ['日期', '據點', '狀態', '營業日ID']
            for loc in Location.query.order_by(Location.id).all():
                if location_id != 'all' and str(loc.id) != location_id: continue
                c_date = start_date
                while c_date <= end_date:
                    bd = BusinessDay.query.filter(and_(BusinessDay.date == c_date, BusinessDay.location_id == loc.id)).first()
                    st_map = {'CLOSED': '已日結', 'PENDING_REPORT': '待確認報表', 'OPEN': '營業中'}
                    st_text = st_map.get(bd.status) if bd else '沒有營業'
                    results_to_write.append([c_date.strftime('%Y-%m-%d'), loc.name, st_text, loc.id])
                    c_date += timedelta(days=1)

        elif report_type == 'periodic_performance':
            header = ['時間單位', '期間 A 銷售額', '期間 A 交易數', '期間 B 銷售額', '期間 B 交易數', '銷售額差異', '增長率']
            def get_pd_csv(s, e, u):
                t_expr = {'year': [extract('year', BusinessDay.date)], 'quarter': [extract('year', BusinessDay.date), case((extract('month', BusinessDay.date) <= 3, 1), (extract('month', BusinessDay.date) <= 6, 2), (extract('month', BusinessDay.date) <= 9, 3), else_=4)], 'month': [extract('year', BusinessDay.date), extract('month', BusinessDay.date)]}
                q = db.session.query(*t_expr[u], func.sum(BusinessDay.total_sales), func.sum(BusinessDay.total_transactions)).filter(BusinessDay.date.between(s, e))
                if location_id != 'all': q = q.filter(BusinessDay.location_id == location_id)
                return q.group_by(*t_expr[u]).order_by(*t_expr[u]).all()
            
            d_a = {tuple(row[:-2]): row[-2:] for row in get_pd_csv(start_date_a, end_date_a, time_unit)}
            d_b = {tuple(row[:-2]): row[-2:] for row in get_pd_csv(start_date_b, end_date_b, time_unit)}
            for k in sorted(list(set(d_a.keys()) | set(d_b.keys()))):
                s_a, t_a = d_a.get(k, (0, 0))
                s_b, t_b = d_b.get(k, (0, 0))
                s_diff = (s_b or 0) - (s_a or 0)
                s_perc = (s_diff / s_a * 100) if s_a else float('inf')
                label = ""
                if time_unit == 'year': label = str(k[0])
                elif time_unit == 'quarter': label = f"{k[0]}-Q{k[1]}"
                elif time_unit == 'month': label = f"{k[0]}-{k[1]:02d}"
                results_to_write.append((label, s_a or 0, t_a or 0, s_b or 0, t_b or 0, s_diff, f"{s_perc:.2f}%" if s_a else "N/A"))
        else:
            flash('此報表類型不支援匯出功能。', 'warning')
            return redirect(url_for('report.query'))

        cw.writerow(header)
        cw.writerows(results_to_write)
        return Response(si.getvalue().encode('utf-8-sig'), mimetype="text/csv", headers={"Content-disposition": f"attachment; filename={report_type}_{date.today().strftime('%Y%m%d')}.csv"})

class SettlementView(ReportConsolidatedAuthorizedView):
    def get(self):
        try: report_date = date.fromisoformat(request.args.get('date', date.today().isoformat()))
        except (ValueError, TypeError): report_date = date.today()

        form = SettlementForm()
        opened_locs = {name for name, in db.session.query(Location.name).join(BusinessDay).filter(BusinessDay.date == report_date).all()}
        closed_reports = db.session.query(BusinessDay).options(db.joinedload(BusinessDay.location)).filter(BusinessDay.date == report_date, BusinessDay.status == 'CLOSED').all()
        
        daily_settlement = DailySettlement.query.filter_by(date=report_date).first()
        is_settled = daily_settlement is not None

        unclosed_locations = opened_locs - {r.location.name for r in closed_reports}
        reports = {r.location.name: r for r in closed_reports}
        grand_total = SettlementService.compute_grand_total(closed_reports, daily_settlement if is_settled else None)

        form.date.data = report_date.isoformat()
        if is_settled:
            form.total_deposit.data = grand_total.H
            form.total_next_day_opening_cash.data = grand_total.I
            if daily_settlement.remarks:
                rmk = json.loads(daily_settlement.remarks)
                for f_rmk in form.remarks:
                    if f_rmk.key.data in rmk: f_rmk.value.data = rmk[f_rmk.key.data]
        else:
            form.total_next_day_opening_cash.data = grand_total.I
            form.total_deposit.data = grand_total.H

        return render_template('report/settlement.html', form=form, report_date=report_date, reports=reports, active_locations_ordered=[name for name in LOCATION_ORDER if name in reports], grand_total=grand_total, all_closed=not unclosed_locations, unclosed_locations=sorted(list(unclosed_locations)), is_settled=is_settled, finance_items=FINANCE_ITEMS, sales_items=SALES_ITEMS, settlement=daily_settlement)

class SaveSettlementView(ReportConsolidatedAuthorizedView):
    def post(self):
        form = SettlementForm()
        if form.validate_on_submit():
            report_date = date.fromisoformat(form.date.data)
            if DailySettlement.query.filter_by(date=report_date).first():
                flash(f"{report_date.strftime('%Y-%m-%d')} 的總結算已歸檔，無法重複儲存。", "warning")
                return redirect(url_for('report.settlement', date=report_date.isoformat()))
            try:
                remarks_dict = {item.key.data: item.value.data for item in form.remarks if item.value.data}
                new_settlement = DailySettlement(date=report_date, total_deposit=form.total_deposit.data, total_next_day_opening_cash=form.total_next_day_opening_cash.data, remarks=json.dumps(remarks_dict))
                db.session.add(new_settlement)
                db.session.commit()
                flash(f"已成功儲存 {report_date.strftime('%Y-%m-%d')} 的總結算資料。", "success")
            except Exception as e:
                db.session.rollback()
                current_app.logger.error("SETTLEMENT_SAVE_ERROR | date=%s | error=%s", report_date, e, exc_info=True)
                flash(f"儲存時發生錯誤：{e}", "danger")
            return redirect(url_for('report.settlement', date=form.date.data or date.today().isoformat()))
        else:
            flash("提交的資料有誤，請重試。 " + " ".join([f" '{getattr(form, field).label.text}': {error}" for field, errors in form.errors.items() for error in errors]), "warning")
            return redirect(url_for('report.settlement', date=form.date.data or date.today().isoformat()))

class PrintSettlementView(ReportConsolidatedAuthorizedView):
    def get(self, date_str):
        try: report_date = date.fromisoformat(date_str)
        except (ValueError, TypeError): flash("無效的日期格式。", "danger"); return redirect(url_for('report.settlement'))
        
        closed_reports = db.session.query(BusinessDay).options(db.joinedload(BusinessDay.location)).filter(BusinessDay.date == report_date, BusinessDay.status == 'CLOSED').all()
        daily_settlement = DailySettlement.query.filter_by(date=report_date).first()
        if not daily_settlement:
            flash("該日期的合併報表尚未結算，無法列印。", "warning")
            return redirect(url_for('report.settlement', date=report_date.isoformat()))
        
        reports = {r.location.name: r for r in closed_reports}
        html_to_render = render_template('report/settlement_print.html', report_date=report_date, reports=reports, active_locations_ordered=[name for name in LOCATION_ORDER if name in reports], grand_total=SettlementService.compute_grand_total(closed_reports, daily_settlement), remarks_data=json.loads(daily_settlement.remarks) if daily_settlement.remarks else {}, finance_items=FINANCE_ITEMS, sales_items=SALES_ITEMS, daily_settlement=daily_settlement, config=current_app.config)
        pdf_bytes = PDFGeneratorService.generate_pdf(html_to_render, request.url_root)
        return Response(pdf_bytes, mimetype="application/pdf", headers={"Content-Disposition": f"attachment;filename=settlement_report_{report_date.isoformat()}.pdf"})

class SettlementStatusAPIView(ReportConsolidatedAuthorizedView):
    def get(self):
        year, month = request.args.get('year', type=int), request.args.get('month', type=int)
        if not year or not month: return jsonify({"error": "Year and month are required"}), 400
        start_date = date(year, month, 1)
        end_date = (start_date + timedelta(days=32)).replace(day=1) - timedelta(days=1)
        
        bd_data = db.session.query(BusinessDay.date, BusinessDay.status, Location.name).join(Location).filter(BusinessDay.date.between(start_date, end_date)).all()
        settled_dates = {s.date for s in db.session.query(DailySettlement.date).filter(DailySettlement.date.between(start_date, end_date)).all()}
        
        day_statuses = defaultdict(lambda: {'opened': set(), 'closed': set()})
        for d, status, loc_name in bd_data:
            day_statuses[d]['opened'].add(loc_name)
            if status == 'CLOSED': day_statuses[d]['closed'].add(loc_name)
            
        response_data, current_date = {}, start_date
        while current_date <= end_date:
            iso_date = current_date.isoformat()
            if current_date in settled_dates: response_data[iso_date] = 'settled'
            elif current_date in day_statuses:
                stats = day_statuses[current_date]
                response_data[iso_date] = 'pending' if len(stats['opened']) > 0 and stats['opened'] == stats['closed'] else 'in_progress'
            else: response_data[iso_date] = 'no_data'
            current_date += timedelta(days=1)
        return jsonify(response_data)

class QueryStatusAPIView(ReportQueryAuthorizedView):
    def get(self):
        year, month = request.args.get('year', type=int), request.args.get('month', type=int)
        if not year or not month: return jsonify({"error": "Year and month are required"}), 400
        start_date = date(year, month, 1)
        end_date = (start_date + timedelta(days=32)).replace(day=1) - timedelta(days=1)
        
        bd_data = db.session.query(BusinessDay.date, BusinessDay.status).filter(BusinessDay.date.between(start_date, end_date)).all()
        day_statuses = defaultdict(list)
        for d, status in bd_data: day_statuses[d].append(status)
        
        response_data, current_date = {}, start_date
        while current_date <= end_date:
            iso_date = current_date.isoformat()
            if current_date in day_statuses:
                statuses = set(day_statuses[current_date])
                response_data[iso_date] = 'in_progress' if 'OPEN' in statuses or 'PENDING_REPORT' in statuses else 'ready'
            else: response_data[iso_date] = 'no_data'
            current_date += timedelta(days=1)
        return jsonify(response_data)

# ==========================================
# Route Registrations
# ==========================================
bp.add_url_rule('/query', endpoint='query', view_func=ReportQueryView.as_view('query'))
bp.add_url_rule('/save_daily_summary_data', endpoint='save_daily_summary_data', view_func=SaveDailySummaryDataView.as_view('save_daily_summary_data'))
bp.add_url_rule('/save_cash_check_data', endpoint='save_cash_check_data', view_func=SaveCashCheckDataView.as_view('save_cash_check_data'))
bp.add_url_rule('/save_transaction_log_data', endpoint='save_transaction_log_data', view_func=SaveTransactionLogDataView.as_view('save_transaction_log_data'))
bp.add_url_rule('/save_daily_cash_summary_data', endpoint='save_daily_cash_summary_data', view_func=SaveDailyCashSummaryDataView.as_view('save_daily_cash_summary_data'))
bp.add_url_rule('/export_csv', endpoint='export_csv', view_func=ExportCSVView.as_view('export_csv'))
bp.add_url_rule('/settlement', endpoint='settlement', view_func=SettlementView.as_view('settlement'))
bp.add_url_rule('/save_settlement', endpoint='save_settlement', view_func=SaveSettlementView.as_view('save_settlement'))
bp.add_url_rule('/settlement/print/<date_str>', endpoint='print_settlement', view_func=PrintSettlementView.as_view('print_settlement'))
bp.add_url_rule('/api/settlement_status', endpoint='settlement_status_api', view_func=SettlementStatusAPIView.as_view('settlement_status_api'))
bp.add_url_rule('/api/query_status', endpoint='query_status_api', view_func=QueryStatusAPIView.as_view('query_status_api'))