# app/routes/cashier_routes.py
import os
import json
from flask import (
    render_template, request, flash, redirect,
    url_for, Blueprint, jsonify, current_app, Response, make_response, abort
)
from flask_login import login_user, logout_user, login_required, current_user
from datetime import date
from urllib.parse import urlparse, urljoin
from flask.views import MethodView

# ORM & Models
from sqlalchemy.orm import contains_eager
from sqlalchemy import and_, case, func
from app.services.pdf_service import PDFGeneratorService
from app.modules.auth.models import User, Role
from app.modules.store.models import Location, Category
from app.modules.daily_ops.models import BusinessDay, DailySettlement
from app.modules.pos.models import Transaction, TransactionItem
from app.modules.system.models import SystemSetting

# Forms
from app.modules.auth.forms import LoginForm, UserForm, RoleForm
from app.modules.store.forms import LocationForm, CategoryForm
from app.modules.daily_ops.forms import StartDayForm, CloseDayForm, ConfirmReportForm, SettlementForm
from app.modules.report.forms import ReportQueryForm
from app.modules.system.forms import POSSettingsForm

from app.core.extensions import db, login_manager, csrf, limiter
from app.core.decorators import admin_required
from app.services.google_service import GoogleIntegrationService
from app.services.backup_service import BackupService

bp = Blueprint("cashier", __name__, url_prefix="/cashier")

# ==========================================
# Helper: Location Access Guard
# ==========================================
def get_authorized_location(location_slug: str):
    """Fetch a Location by slug and verify current user has access.
    Aborts with 404 if the slug is invalid, 403 if user lacks access.
    Admin role bypasses the location-binding check automatically.
    """
    location = Location.query.filter_by(slug=location_slug).first_or_404()
    if not current_user.can_access_location(location_slug):
        abort(403)
    return location

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ==========================================
# Base Views (OOP Inheritance)
# ==========================================
from functools import wraps


def require_pos_operate(f):
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.can('pos_operate_cashier'):
            from flask import flash, redirect, url_for
            flash("權限不足：您不具備「據點收銀台操作」權限。", "danger")
            return redirect(url_for('cashier.dashboard'))
        return f(*args, **kwargs)
    return decorated_function

def require_report_view(f):
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not (current_user.can('report_view_daily') or current_user.can('report_edit_daily') or current_user.can('pos_operate_cashier')):
            from flask import flash, redirect, url_for
            flash("權限不足：您不具備查閱據點日報表的權限。", "danger")
            return redirect(url_for('cashier.dashboard'))
        return f(*args, **kwargs)
    return decorated_function

class PosAuthorizedView(MethodView):
    decorators = [login_required, require_pos_operate]

class ReportAuthorizedView(MethodView):
    decorators = [login_required, require_report_view]
class AdminBaseView(MethodView):
    """Base class for admin views, requires login and admin privileges"""
    decorators = [login_required, admin_required]

# ==========================================
# Authentication & Core Dashboard
# ==========================================
class IndexView(MethodView):
    decorators = [login_required]
    def get(self):
        return redirect(url_for('main.index'))

class DashboardView(MethodView):
    decorators = [login_required]
    def get(self):
        today = date.today()
        locations = (
            db.session.query(Location)
            .outerjoin(BusinessDay, and_(Location.id == BusinessDay.location_id, BusinessDay.date == today))
            .options(contains_eager(Location.business_days))
            .order_by(Location.id)
            .all()
        )
        locations = [loc for loc in locations if current_user.can_access_location(loc.slug)]
        locations_status = {}
        for location in locations:
            business_day = next(iter(location.business_days), None)
            total_sales_with_income = business_day.total_sales if business_day else 0
            if business_day:
                other_income_totals = db.session.query(Category.name, func.sum(TransactionItem.price)) \
                    .join(TransactionItem.transaction).join(Transaction.business_day).join(TransactionItem.category) \
                    .filter(BusinessDay.id == business_day.id, Category.category_type == 'other_income') \
                    .group_by(Category.name).all()
                for name, total in other_income_totals:
                    total_sales_with_income += total

            if business_day is None:
                status_info = {"business_day_id": None, "status_text": "尚未開帳", "message": "點擊以開始本日營業作業。", "badge_class": "bg-secondary", "url": url_for("cashier.start_day", location_slug=location.slug)}
            elif business_day.status == "OPEN":
                status_info = {"business_day_id": business_day.id, "status_text": "營業中", "message": f"本日銷售額: ${total_sales_with_income:,.0f}", "badge_class": "bg-success", "url": url_for("cashier.pos", location_slug=location.slug)}
            elif business_day.status == "PENDING_REPORT":
                status_info = {"business_day_id": business_day.id, "status_text": "待確認報表", "message": "點擊以檢視並確認本日報表。", "badge_class": "bg-warning text-dark", "url": url_for("cashier.daily_report", location_slug=location.slug)}
            elif business_day.status == "CLOSED":
                status_info = {"business_day_id": business_day.id, "status_text": "已日結", "message": "本日帳務已結算，僅供查閱。", "badge_class": "bg-primary", "url": url_for("cashier.daily_report", location_slug=location.slug)}
            else:
                # Fallback for unexpected status values - prevents NameError / 500
                status_info = {"business_day_id": business_day.id, "status_text": "狀態異常", "message": "該據點狀態異常，請聯繫管理員。", "badge_class": "bg-secondary", "url": url_for("cashier.dashboard")}
            locations_status[location] = status_info
        return render_template("cashier/dashboard.html", today_date=today.strftime("%Y-%m-%d"), locations_status=locations_status)

class LoginView(MethodView):
    """Legacy redirect: /cashier/login -> /login (backward compatibility)"""
    def get(self):  return redirect(url_for('auth.login', next=request.args.get('next', '')))
    def post(self): return redirect(url_for('auth.login', next=request.args.get('next', '')))

class LogoutView(MethodView):
    """Legacy redirect: /cashier/logout -> /logout"""
    decorators = [login_required]
    def get(self):
        current_app.logger.info("LOGOUT | user_id=%s | username=%s | ip=%s", current_user.id, current_user.username, request.remote_addr)
        logout_user()
        flash("您已成功登出。", "info")
        return redirect(url_for('auth.login'))

# ==========================================
# Settings & Backups
# ==========================================
class SettingsView(MethodView):
    decorators = [login_required]

    def get(self):
        if not current_user.can('pos_operate_cashier'):
            flash('您沒有權限存取營運系統設定。', 'danger')
            return redirect(url_for('cashier.dashboard'))

        form = POSSettingsForm()
        # Set default values from DB
        form.pos_checkout_delay_seconds.data = int(SystemSetting.get('pos_checkout_delay_seconds', '3'))

        return render_template("cashier/pos_settings.html", form=form)

    def post(self):
        if not current_user.can('pos_operate_cashier'):
            flash('您沒有權限存取營運系統設定。', 'danger')
            return redirect(url_for('cashier.dashboard'))

        form = POSSettingsForm()
        if form.validate_on_submit():
            SystemSetting.set('pos_checkout_delay_seconds', str(form.pos_checkout_delay_seconds.data) if form.pos_checkout_delay_seconds.data else '3')

            flash('POS 營運設定已儲存！', 'success')
            return redirect(url_for('cashier.settings'))
        return self.get()

# Removed RebuildBackupView and ManualInstanceBackupView

# ==========================================
# POS & Daily Operations
# ==========================================
class StartDayView(PosAuthorizedView):
    def get(self, location_slug):
        location = get_authorized_location(location_slug)
        today = date.today()
        if BusinessDay.query.filter_by(date=today, location_id=location.id).first():
            flash(f'據點 "{location.name}" 今日已開帳或已日結，無法重複操作。', "warning")
            return redirect(url_for("cashier.dashboard"))
        return render_template("cashier/start_day_form.html", location=location, today_date=today.strftime("%Y-%m-%d"), form=StartDayForm())

    def post(self, location_slug):
        location = get_authorized_location(location_slug)
        today = date.today()
        form = StartDayForm()
        if form.validate_on_submit():
            bd = BusinessDay(date=today, location=location, location_notes=form.location_notes.data, status="OPEN", opening_cash=form.opening_cash.data)
            db.session.add(bd)
            db.session.commit()
            flash(f'據點 "{location.name}" 開店成功！現在可以開始記錄交易。', "success")
            return redirect(url_for("cashier.pos", location_slug=location.slug))
        return render_template("cashier/start_day_form.html", location=location, today_date=today.strftime("%Y-%m-%d"), form=form)

class ReopenDayView(AdminBaseView):
    def post(self, location_slug):
        location = get_authorized_location(location_slug)
        today = date.today()
        business_day = BusinessDay.query.filter_by(date=today, location_id=location.id).first()
        
        if not business_day:
            flash("找不到今日的營業紀錄。", "danger")
        elif business_day.status == "OPEN":
            flash("此據點已經在營業中。", "warning")
        else:
            business_day.status = "OPEN"
            sgt = DailySettlement.query.filter_by(date=today).first()
            if sgt:
                db.session.delete(sgt)
            db.session.commit()
            current_app.logger.info(f"Admin {current_user.username} 重新開啟了據點 {location.name} 的本日營業狀態。")
            flash(f'據點 "{location.name}" 已成功強制切回「營業中」，可以繼續進行 POS 操作。', "success")
        return redirect(url_for("cashier.dashboard"))

class POSView(PosAuthorizedView):
    def get(self, location_slug):
        location = get_authorized_location(location_slug)
        business_day = BusinessDay.query.filter_by(date=date.today(), location_id=location.id, status="OPEN").first()
        if not business_day:
            flash(f'據點 "{location.name}" 今日尚未開店營業。', "warning")
            return redirect(url_for("cashier.dashboard"))

        categories = Category.query.filter_by(location_id=location.id).order_by(Category.id).all()
        other_income_totals = db.session.query(Category.name, func.sum(TransactionItem.price)) \
            .join(TransactionItem.transaction).join(Transaction.business_day).join(TransactionItem.category) \
            .filter(BusinessDay.id == business_day.id, Category.category_type == 'other_income') \
            .group_by(Category.name).all()

        donation_total = 0
        other_total = 0
        for name, total in other_income_totals:
            total_val = total or 0
            if name == '捐款': donation_total = total_val
            else: other_total += total_val

        checkout_delay = SystemSetting.get('pos_checkout_delay_seconds', '3')

        response = make_response(render_template("cashier/pos.html",
                               location=location, today_date=date.today().strftime("%Y-%m-%d"),
                               business_day=business_day, categories=categories,
                               donation_total=donation_total, other_total=other_total,
                               checkout_delay=checkout_delay))
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        return response

class RecordTransactionView(PosAuthorizedView):
    decorators = [login_required]
    
    def post(self):
        data = request.get_json(silent=True)
        if not data:
            return jsonify({"success": False, "error": "無效的請求格式"}), 400

        location_slug = data.get("location_slug", "").strip()
        items_data = data.get("items", [])
        cash_received = data.get("cash_received", 0)
        change_given = data.get("change_given", 0)

        if not location_slug:
            return jsonify({"success": False, "error": "缺少據點資訊"}), 400
        if not items_data:
            return jsonify({"success": False, "error": "交易內容不可為空"}), 400

        location = Location.query.filter_by(slug=location_slug).first()
        if not location:
            return jsonify({"success": False, "error": f"找不到據點: {location_slug}"}), 404

        if not current_user.can_access_location(location_slug):
            return jsonify({"success": False, "error": "您無權操作此據點"}), 403

        business_day = BusinessDay.query.filter_by(
            date=date.today(), location_id=location.id, status="OPEN"
        ).first()
        if not business_day:
            return jsonify({"success": False, "error": "今日尚無開啟中的業務日，請先開帳"}), 409

        try:
            # Separate product/discount items from other_income items
            # The JS sends each item with price + category_id
            product_items = [i for i in items_data if i.get("price", 0) > 0]
            discount_items = [i for i in items_data if i.get("price", 0) < 0]
            
            total_amount = sum(i.get("price", 0) for i in items_data)
            total_positive = sum(i.get("price", 0) for i in product_items)
            item_count = len([i for i in items_data if i.get("price", 0) > 0])
            
            discount_json = ",".join([str(abs(i.get("price", 0))) for i in discount_items]) if discount_items else None

            txn = Transaction(
                amount=total_amount,
                item_count=item_count,
                business_day_id=business_day.id,
                cash_received=float(cash_received),
                change_given=float(change_given),
                discounts=discount_json
            )
            db.session.add(txn)
            db.session.flush()  # Get txn.id without committing

            for item in items_data:
                cat_id = item.get("category_id")
                price = float(item.get("price", 0))
                if cat_id is None:
                    # No category (manual input) — skip creating TransactionItem
                    continue
                ti = TransactionItem(
                    price=price,
                    transaction_id=txn.id,
                    category_id=int(cat_id)
                )
                db.session.add(ti)

            # Update BusinessDay aggregates
            business_day.total_sales = (business_day.total_sales or 0) + max(total_amount, 0)
            business_day.total_items = (business_day.total_items or 0) + item_count
            business_day.total_transactions = (business_day.total_transactions or 0) + 1

            db.session.commit()

            # Recalculate other income totals to return to frontend
            from sqlalchemy import func as sql_func
            other_income_totals = db.session.query(Category.name, sql_func.sum(TransactionItem.price)) \
                .join(TransactionItem.transaction).join(Transaction.business_day).join(TransactionItem.category) \
                .filter(BusinessDay.id == business_day.id, Category.category_type == 'other_income') \
                .group_by(Category.name).all()

            donation_total = 0
            other_total = 0
            for name, total in other_income_totals:
                v = total or 0
                if name == '捐款':
                    donation_total = v
                else:
                    other_total += v

            current_app.logger.info(
                "TRANSACTION | business_day=%s | location=%s | amount=%.2f | user=%s",
                business_day.id, location_slug, total_amount, current_user.username
            )

            return jsonify({
                "success": True,
                "total_sales": business_day.total_sales,
                "total_items": business_day.total_items,
                "total_transactions": business_day.total_transactions,
                "donation_total": donation_total,
                "other_total": other_total
            })

        except Exception as e:
            db.session.rollback()
            current_app.logger.error("TRANSACTION_ERROR | %s | user=%s", str(e), current_user.username, exc_info=True)
            return jsonify({"success": False, "error": "伺服器內部錯誤，交易未記錄"}), 500

class CloseDayView(PosAuthorizedView):
    def get(self, location_slug):
        location = get_authorized_location(location_slug)
        business_day = BusinessDay.query.filter(BusinessDay.date == date.today(), BusinessDay.location_id == location.id).filter(BusinessDay.status.in_(["OPEN", "PENDING_REPORT"])).first()
        if not business_day:
            flash(f'據點 "{location.name}" 今日並非營業中狀態，無法進行日結。', "warning")
            return redirect(url_for("cashier.dashboard"))
        return render_template("cashier/close_day_form.html", location=location, today_date=date.today().strftime("%Y-%m-%d"), denominations=[1000, 500, 200, 100, 50, 10, 5, 1], form=CloseDayForm())

    def post(self, location_slug):
        location = get_authorized_location(location_slug)
        business_day = BusinessDay.query.filter(BusinessDay.date == date.today(), BusinessDay.location_id == location.id).filter(BusinessDay.status.in_(["OPEN", "PENDING_REPORT"])).first()
        form = CloseDayForm()
        if form.validate_on_submit():
            try:
                tot, bd_json = 0, {}
                for d in [1000, 500, 200, 100, 50, 10, 5, 1]:
                    c = request.form.get(f"count_{d}", 0, type=int)
                    tot += c * d
                    bd_json[d] = c
                business_day.closing_cash = tot
                business_day.cash_breakdown = json.dumps(bd_json)
                business_day.status = "PENDING_REPORT"
                db.session.commit()
                flash("現金盤點完成！請核對最後的每日報表。", "success")
                return redirect(url_for("cashier.daily_report", location_slug=location.slug))
            except Exception as e:
                db.session.rollback()
                flash(f"處理日結時發生錯誤：{e}", "danger")
        return self.get(location_slug)

class DailyReportView(ReportAuthorizedView):
    def get(self, location_slug):
        location = get_authorized_location(location_slug)
        try:
            report_date = date.fromisoformat(request.args.get('date', date.today().isoformat()))
        except ValueError:
            flash("日期格式無效。", "danger")
            return redirect(url_for("cashier.dashboard"))

        bd = BusinessDay.query.filter(BusinessDay.date == report_date, BusinessDay.location_id == location.id, BusinessDay.status.in_(["PENDING_REPORT", "CLOSED"])).first()
        if not bd:
            flash(f'找不到據點 "{location.name}" {report_date.strftime("%Y-%m-%d")} 的日結報表資料。', "warning")
            return redirect(url_for("cashier.dashboard"))

        from app.services.pos_service import POSService
        sales_total, other_income_total = POSService.calculate_daily_totals(bd.id)
        
        expected_total = (bd.opening_cash or 0) + sales_total + other_income_total
        difference = (bd.closing_cash or 0) - expected_total
        bd.total_sales = sales_total
        bd.expected_cash = expected_total
        bd.cash_diff = difference

        return render_template("cashier/daily_report.html", day=bd, other_income_total=other_income_total, expected_total=expected_total, difference=difference, form=ConfirmReportForm())

class ConfirmReportView(ReportAuthorizedView):
    def post(self, location_slug):
        report_date_str = request.form.get('report_date')
        if not report_date_str:
            flash("請求缺少日期參數。", "danger")
            return redirect(url_for("cashier.dashboard"))
        try: report_date = date.fromisoformat(report_date_str)
        except ValueError: flash("日期格式無效。", "danger"); return redirect(url_for("cashier.dashboard"))
        
        location = get_authorized_location(location_slug)
        bd = BusinessDay.query.filter_by(date=report_date, location_id=location.id, status="PENDING_REPORT").first()
        if not bd:
            flash("找不到待確認的報表，或該報表已被確認。", "warning")
            return redirect(url_for("cashier.dashboard"))
        
        form = ConfirmReportForm()
        if form.validate_on_submit():
            try:
                bd.signature_operator = request.form.get('sig_operator')
                bd.signature_reviewer = request.form.get('sig_reviewer')
                bd.signature_cashier = request.form.get('sig_cashier')
                bd.status = "CLOSED"
                
                from app.services.pos_service import POSService
                sales_total, other_income_total = POSService.calculate_daily_totals(bd.id)
                
                bd.total_sales = sales_total
                bd.expected_cash = (bd.opening_cash or 0) + (bd.total_sales or 0) + other_income_total
                bd.cash_diff = (bd.closing_cash or 0) - bd.expected_cash
                
                db.session.commit()
                
                header = ["日期", "據點", "開店準備金", "本日銷售總額", "帳面總額", "盤點現金合計", "帳差", "交易筆數", "銷售件數"]
                report_data = [bd.date.strftime("%Y-%m-%d"), bd.location.name, bd.opening_cash, bd.total_sales, bd.expected_cash, bd.closing_cash, bd.cash_diff, bd.total_transactions, bd.total_items]
                current_app.task_queue.enqueue('app.services.google_service.GoogleIntegrationService.write_report_to_sheet_task', args=(location.id, report_data, header), job_timeout='10m')
                flash(f'據點 "{location.name}" 本日營業已成功歸檔！正在背景同步至雲端...', "success")
                return redirect(url_for("cashier.daily_report", location_slug=location.slug, date=report_date.isoformat()))
            except Exception as e:
                db.session.rollback()
                flash(f"歸檔時發生錯誤：{e}", "danger")
        return redirect(url_for('cashier.daily_report', location_slug=location.slug, date=report_date.isoformat()))

class PrintReportView(ReportAuthorizedView):
    def post(self, location_slug):
        location = get_authorized_location(location_slug)
        bd = BusinessDay.query.filter(BusinessDay.date == date.today(), BusinessDay.location_id == location.id).first_or_404()
        
        other_income_total = db.session.query(func.sum(TransactionItem.price)).join(TransactionItem.transaction).join(Transaction.business_day).join(TransactionItem.category).filter(
            BusinessDay.id == bd.id, Category.category_type == 'other_income'
        ).scalar() or 0

        expected_total = (bd.opening_cash or 0) + (bd.total_sales or 0) + other_income_total
        difference = (bd.closing_cash or 0) - expected_total
        
        signatures = {
            'operator': request.form.get('sig_operator') if request.form.get('sig_operator') and request.form.get('sig_operator') != 'data:,' else bd.signature_operator,
            'reviewer': request.form.get('sig_reviewer') if request.form.get('sig_reviewer') and request.form.get('sig_reviewer') != 'data:,' else bd.signature_reviewer,
            'cashier': request.form.get('sig_cashier') if request.form.get('sig_cashier') and request.form.get('sig_cashier') != 'data:,' else bd.signature_cashier
        }
        
        html_to_render = render_template("cashier/report_print.html", day=bd, other_income_total=other_income_total, expected_total=expected_total, difference=difference, signatures=signatures)
        pdf = PDFGeneratorService.generate_pdf(html_to_render, request.url_root)
        return Response(pdf, mimetype="application/pdf", headers={"Content-Disposition": f"attachment;filename=daily_report_{location.slug}_{date.today().strftime('%Y%m%d')}.pdf"})

# ==========================================
# Route Registrations
# ==========================================
bp.add_url_rule('/', endpoint='index', view_func=IndexView.as_view('index'))
bp.add_url_rule('/dashboard', endpoint='dashboard', view_func=DashboardView.as_view('dashboard'))
bp.add_url_rule('/login', endpoint='login', view_func=LoginView.as_view('login'))
bp.add_url_rule('/logout', endpoint='logout', view_func=LogoutView.as_view('logout'))
bp.add_url_rule('/settings', endpoint='settings', view_func=SettingsView.as_view('settings'))
bp.add_url_rule('/start_day/<location_slug>', endpoint='start_day', view_func=StartDayView.as_view('start_day'))
bp.add_url_rule('/reopen_day/<location_slug>', endpoint='reopen_day', view_func=ReopenDayView.as_view('reopen_day'))
bp.add_url_rule('/pos/<location_slug>', endpoint='pos', view_func=POSView.as_view('pos'))
bp.add_url_rule('/record_transaction', endpoint='record_transaction', view_func=RecordTransactionView.as_view('record_transaction'))
bp.add_url_rule('/close_day/<location_slug>', endpoint='close_day', view_func=CloseDayView.as_view('close_day'))
bp.add_url_rule('/report/<location_slug>', endpoint='daily_report', view_func=DailyReportView.as_view('daily_report'))
bp.add_url_rule('/confirm_report/<location_slug>', endpoint='confirm_report', view_func=ConfirmReportView.as_view('confirm_report'))
bp.add_url_rule('/report/<location_slug>/print', endpoint='print_report', view_func=PrintReportView.as_view('print_report'))