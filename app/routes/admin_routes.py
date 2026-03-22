import os
import json
from flask import (
    render_template, request, flash, redirect, url_for,
    Blueprint, jsonify, current_app, Response
)
from flask_login import login_required, current_user
from datetime import date, datetime
from flask.views import MethodView

# ORM & Models
from sqlalchemy.orm import contains_eager
from sqlalchemy import and_, case
from sqlalchemy.exc import IntegrityError
from sqlalchemy.sql import func
from app.modules.auth.models import User, Role, PERMISSION_STRUCTURE
from app.modules.store.models import Location, Category
from app.modules.daily_ops.models import BusinessDay, DailySettlement
from app.modules.pos.models import Transaction, TransactionItem
from app.modules.system.models import SystemSetting

# Forms
from app.modules.auth.forms import LoginForm, UserForm, RoleForm
from app.modules.store.forms import LocationForm, CategoryForm
from app.modules.daily_ops.forms import StartDayForm, CloseDayForm, ConfirmReportForm, SettlementForm
from app.modules.report.forms import ReportQueryForm
from app.modules.system.forms import GlobalSettingsForm

from app.services.google_service import GoogleIntegrationService

from app.core.extensions import db, login_manager, csrf
from app.core.decorators import admin_required

bp = Blueprint('admin', __name__, url_prefix='/admin')

# ==========================================
# Base Views (OOP Inheritance)
# ==========================================

from functools import wraps
from flask import abort

def require_permission(perm):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.can(perm):
                flash(f"存取遭拒：您不具備此系統管理模組的權限。 ({perm})", "danger")
                return redirect(url_for('main.index'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

class AdminLocationsView(MethodView):
    decorators = [login_required, require_permission('admin_locations')]

class AdminUsersView(MethodView):
    decorators = [login_required, require_permission('admin_users')]

class AdminRolesView(MethodView):
    decorators = [login_required, require_permission('admin_roles')]

class AdminSystemView(MethodView):
    decorators = [login_required, require_permission('admin_system')]

class ReportEditDailyView(MethodView):
    decorators = [login_required, require_permission('report_edit_daily')]

class AdminBaseView(MethodView):
    decorators = [login_required]
# ==========================================
# Location Management
# ==========================================
class LocationListView(AdminLocationsView):
    def get(self):
        locations = Location.query.order_by(Location.id).all()
        return render_template('admin/locations.html', locations=locations)

class LocationAddView(AdminLocationsView):
    def get(self):
        form = LocationForm()
        return render_template('admin/location_form.html', form=form, form_title='新增據點')
        
    def post(self):
        form = LocationForm()
        if form.validate_on_submit():
            new_location = Location(name=form.name.data, slug=form.slug.data)
            db.session.add(new_location)
            db.session.commit()
            flash('據點已新增', 'success')
            return redirect(url_for('admin.list_locations'))
        return render_template('admin/location_form.html', form=form, form_title='新增據點')

class LocationEditView(AdminLocationsView):
    def get(self, location_id):
        location = Location.query.get_or_404(location_id)
        form = LocationForm(obj=location)
        return render_template('admin/location_form.html', form=form, form_title='編輯據點')
        
    def post(self, location_id):
        location = Location.query.get_or_404(location_id)
        form = LocationForm(obj=location)
        if form.validate_on_submit():
            form.populate_obj(location)
            db.session.commit()
            flash('據點已更新', 'success')
            return redirect(url_for('admin.list_locations'))
        return render_template('admin/location_form.html', form=form, form_title='編輯據點')

class LocationDeleteView(AdminLocationsView):
    def post(self, location_id):
        location = Location.query.get_or_404(location_id)
        if location.business_days:
            flash(f'錯誤：無法刪除據點 "{location.name}"，因為它仍有相關的營業日紀錄。', 'danger')
        else:
            db.session.delete(location)
            db.session.commit()
            flash('據點已刪除', 'success')
        return redirect(url_for('admin.list_locations'))

# ==========================================
# Category Management
# ==========================================
def get_category_form_data(form, category):
    category.name = form.name.data
    category.color = form.color.data
    category.category_type = form.category_type.data
    rules = {}
    ctype = form.category_type.data
    if ctype in ['buy_n_get_m', 'buy_x_get_x_minus_1', 'buy_odd_even'] and form.rule_target_category_id.data is not None:
        rules['target_category_id'] = form.rule_target_category_id.data
    if ctype == 'buy_n_get_m':
        if form.rule_buy_n.data is not None: rules['buy_n'] = form.rule_buy_n.data
        if form.rule_get_m.data is not None: rules['get_m_free'] = form.rule_get_m.data
    category.set_rules(rules) if rules else setattr(category, 'discount_rules', None)


class CategoryListView(AdminLocationsView):
    decorators = [login_required, admin_required, csrf.exempt]
    
    def get(self, location_id):
        location = Location.query.get_or_404(location_id)
        product_categories_query = Category.query.filter_by(location_id=location.id, category_type='product').all()
        product_categories_choices = [(0, '--- 全部商品 ---')] + [(p.id, p.name) for p in product_categories_query]
        categories = Category.query.filter_by(location_id=location.id).order_by(Category.id).all()
        return render_template('admin/categories.html', location=location, categories=categories, product_categories_choices=product_categories_choices)

    def post(self, location_id):
        location = Location.query.get_or_404(location_id)
        try:
            for category in location.categories:
                cat_id = category.id
                prefix = f'category-{cat_id}-'
                if request.form.get(prefix + 'name') is not None:
                    category.name = request.form.get(prefix + 'name')
                    category.color = request.form.get(prefix + 'color')
                    category.category_type = request.form.get(prefix + 'type')
                    rules = {}
                    ctype = category.category_type
                    if ctype in ['buy_n_get_m', 'buy_x_get_x_minus_1', 'buy_odd_even', 'product_discount_percent']:
                        target_id = request.form.get(f'rule-{cat_id}-target_category_id')
                        if target_id: rules['target_category_id'] = int(target_id)
                    if ctype == 'buy_n_get_m':
                        buy_n = request.form.get(f'rule-{cat_id}-buy_n')
                        get_m = request.form.get(f'rule-{cat_id}-get_m_free')
                        if buy_n: rules['buy_n'] = int(buy_n)
                        if get_m: rules['get_m_free'] = int(get_m)
                    if ctype in ['discount_percent', 'product_discount_percent']:
                        percent = request.form.get(f'rule-{cat_id}-percent')
                        if percent: rules['percent'] = float(percent)
                    category.set_rules(rules) if rules else setattr(category, 'discount_rules', None)

            # New categories
            new_names = request.form.getlist('new-name')
            new_colors = request.form.getlist('new-color')
            new_types = request.form.getlist('new-type')
            new_targets = request.form.getlist('new-rule-target_category_id')
            new_buy_ns = request.form.getlist('new-rule-buy_n')
            new_get_ms = request.form.getlist('new-rule-get_m_free')

            for i, name in enumerate(new_names):
                if name.strip():
                    new_category = Category(
                        name=name.strip(),
                        color=new_colors[i] if i < len(new_colors) else '#cccccc',
                        location_id=location.id,
                        category_type=new_types[i] if i < len(new_types) else 'product'
                    )
                    new_rules = {}
                    ctype = new_types[i] if i < len(new_types) else 'product'
                    if ctype in ['buy_n_get_m', 'buy_x_get_x_minus_1', 'buy_odd_even', 'product_discount_percent'] and i < len(new_targets) and new_targets[i]:
                        new_rules['target_category_id'] = int(new_targets[i])
                    if ctype == 'buy_n_get_m':
                        if i < len(new_buy_ns) and new_buy_ns[i]: new_rules['buy_n'] = int(new_buy_ns[i])
                        if i < len(new_get_ms) and new_get_ms[i]: new_rules['get_m_free'] = int(new_get_ms[i])
                    if ctype in ['discount_percent', 'product_discount_percent']:
                        new_percents = request.form.getlist('new-rule-percent')
                        if i < len(new_percents) and new_percents[i]: new_rules['percent'] = float(new_percents[i])
                    
                    if new_rules:
                        new_category.set_rules(new_rules)
                    db.session.add(new_category)
            db.session.commit()
            flash('所有變更已成功儲存！', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'儲存失敗，發生錯誤：{e}', 'danger')
        return redirect(url_for('admin.list_categories', location_id=location.id))

class CategoryAddView(AdminLocationsView):
    def get(self, location_id):
        location = Location.query.get_or_404(location_id)
        form = CategoryForm(location_id=location.id)
        return render_template('admin/category_form.html', form=form, form_title='新增商品類別', location=location)

    def post(self, location_id):
        location = Location.query.get_or_404(location_id)
        form = CategoryForm(location_id=location.id)
        if form.validate_on_submit():
            new_category = Category(location_id=location.id)
            get_category_form_data(form, new_category)
            db.session.add(new_category)
            db.session.commit()
            flash(f'類別 "{new_category.name}" 已成功新增。', 'success')
            return redirect(url_for('admin.list_categories', location_id=location.id))
        return render_template('admin/category_form.html', form=form, form_title='新增商品類別', location=location)

class CategoryEditView(AdminLocationsView):
    def get(self, category_id):
        category = Category.query.get_or_404(category_id)
        location = category.location
        form = CategoryForm(location_id=location.id, obj=category)
        rules = category.get_rules()
        form.rule_target_category_id.data = rules.get('target_category_id')
        form.rule_buy_n.data = rules.get('buy_n')
        form.rule_get_m.data = rules.get('get_m_free')
        return render_template('admin/category_form.html', form=form, form_title='編輯商品類別', location=location, category=category)

    def post(self, category_id):
        category = Category.query.get_or_404(category_id)
        location = category.location
        form = CategoryForm(location_id=location.id, obj=category)
        if form.validate_on_submit():
            get_category_form_data(form, category)
            db.session.commit()
            flash(f'類別 "{category.name}" 已更新。', 'success')
            return redirect(url_for('admin.list_categories', location_id=location.id))
        return render_template('admin/category_form.html', form=form, form_title='編輯商品類別', location=location, category=category)

class CategoryDeleteView(AdminLocationsView):
    def post(self, category_id):
        category = Category.query.get_or_404(category_id)
        location_id = category.location_id
        if TransactionItem.query.filter_by(category_id=category_id).first():
            flash(f'錯誤：無法刪除類別 "{category.name}"，因為已有交易紀錄。', 'danger')
        elif Category.query.filter(Category.discount_rules.like(f'%"{category_id}"%')).first():
            flash(f'錯誤：無法刪除類別 "{category.name}"，因為被其他規則引用。', 'danger')
        else:
            try:
                db.session.delete(category)
                db.session.commit()
                flash('類別已刪除。', 'success')
            except Exception as e:
                db.session.rollback()
                flash(f'刪除失敗: {e}', 'danger')
        return redirect(url_for('admin.list_categories', location_id=location_id))

# ==========================================
# User and Role Management
# ==========================================
class UserListView(AdminUsersView):
    def get(self):
        users = User.query.order_by(User.id).all()
        return render_template('admin/users.html', users=users)

class UserAddView(AdminUsersView):
    def get(self):
        form = UserForm(user=None)
        return render_template('admin/user_form.html', form=form, form_title="建立新使用者")

    def post(self):
        form = UserForm(user=None)
        if form.validate_on_submit():
            user = User(username=form.username.data)
            if form.password.data: user.set_password(form.password.data)
            for role_id in form.roles.data:
                user.roles.append(Role.query.get(role_id))
            db.session.add(user)
            db.session.commit()
            flash('新使用者已建立。', 'success')
            return redirect(url_for('admin.list_users'))
        return render_template('admin/user_form.html', form=form, form_title="建立新使用者")

class UserEditView(AdminUsersView):
    def get(self, user_id):
        user = User.query.get_or_404(user_id)
        form = UserForm(user=user, obj=user)
        form.roles.data = [role.id for role in user.roles]
        return render_template('admin/user_form.html', form=form, form_title="編輯使用者", user=user)

    def post(self, user_id):
        user = User.query.get_or_404(user_id)
        form = UserForm(user=user, obj=user)
        if form.validate_on_submit():
            user.username = form.username.data
            if form.password.data: user.set_password(form.password.data)
            user.roles = []
            for role_id in form.roles.data: user.roles.append(Role.query.get(role_id))
            db.session.commit()
            flash('使用者資料已更新。', 'success')
            return redirect(url_for('admin.list_users'))
        return render_template('admin/user_form.html', form=form, form_title="編輯使用者", user=user)

class UserDeleteView(AdminUsersView):
    def post(self, user_id):
        user = User.query.get_or_404(user_id)
        db.session.delete(user)
        db.session.commit()
        flash('使用者已刪除。', 'success')
        return redirect(url_for('admin.list_users'))

class RoleListView(AdminRolesView):
    def get(self):
        roles = Role.query.order_by(Role.id).all()
        return render_template('admin/roles.html', roles=roles)

class RoleAddView(AdminRolesView):
    def get(self):
        form = RoleForm()
        from app.modules.auth.models import PERMISSION_STRUCTURE
        return render_template('admin/role_form.html', form=form, form_title="建立新角色", permission_structure=PERMISSION_STRUCTURE, all_locations=Location.query.all())

    def post(self):
        form = RoleForm()
        if form.validate_on_submit():
            role = Role(name=form.name.data, permissions=','.join(form.permissions.data))
            
            if form.locations.data:
                role.locations = Location.query.filter(Location.id.in_(form.locations.data)).all()
                
            db.session.add(role)
            db.session.commit()
            flash('新角色已建立。', 'success')
            return redirect(url_for('admin.list_roles'))
            
        from app.modules.auth.models import PERMISSION_STRUCTURE
        return render_template('admin/role_form.html', form=form, form_title="建立新角色", permission_structure=PERMISSION_STRUCTURE, all_locations=Location.query.all())

class RoleEditView(AdminRolesView):
    def get(self, role_id):
        role = Role.query.get_or_404(role_id)
        form = RoleForm(obj=role)
        form.permissions.data = role.get_permissions()
        form.locations.data = [loc.id for loc in role.locations]
        
        from app.modules.auth.models import PERMISSION_STRUCTURE
        return render_template('admin/role_form.html', form=form, form_title="編輯角色", permission_structure=PERMISSION_STRUCTURE, all_locations=Location.query.all())

    def post(self, role_id):
        role = Role.query.get_or_404(role_id)
        form = RoleForm(obj=role)
        if form.validate_on_submit():
            role.name = form.name.data
            role.permissions = ','.join(form.permissions.data)
            
            role.locations = []
            if form.locations.data:
                role.locations = Location.query.filter(Location.id.in_(form.locations.data)).all()
                
            db.session.commit()
            flash('角色已更新。', 'success')
            return redirect(url_for('admin.list_roles'))
            
        from app.modules.auth.models import PERMISSION_STRUCTURE
        return render_template('admin/role_form.html', form=form, form_title="編輯角色", permission_structure=PERMISSION_STRUCTURE, all_locations=Location.query.all())

class RoleDeleteView(AdminRolesView):
    def post(self, role_id):
        role = Role.query.get_or_404(role_id)
        db.session.delete(role)
        db.session.commit()
        flash('角色已刪除。', 'success')
        return redirect(url_for('admin.list_roles'))

# ==========================================
# Force Close Operations
# ==========================================
class ForceCloseDayView(ReportEditDailyView):
    def get(self, business_day_id):
        bd = BusinessDay.query.get_or_404(business_day_id)
        return render_template('admin/force_close_day.html', location=bd.location, today_date=bd.date.strftime("%Y-%m-%d"), denominations=[1000, 500, 200, 100, 50, 10, 5, 1], form=CloseDayForm())

    def post(self, business_day_id):
        bd = BusinessDay.query.get_or_404(business_day_id)
        form = CloseDayForm()
        if form.validate_on_submit():
            try:
                total, breakdown = 0, {}
                for d in [1000, 500, 200, 100, 50, 10, 5, 1]:
                    count = request.form.get(f"count_{d}", 0, type=int)
                    total += count * d
                    breakdown[d] = count
                bd.closing_cash = total
                bd.cash_breakdown = json.dumps(breakdown)
                bd.status = "PENDING_REPORT"
                db.session.commit()
                flash(f"已完成日結！請前往審核。", "success")
                return redirect(url_for('cashier.daily_report', location_slug=bd.location.slug, date=bd.date.isoformat()))
            except Exception as e:
                db.session.rollback()
                flash(f"錯誤：{e}", "danger")
        return self.get(business_day_id)

class NewForceCloseDayView(AdminBaseView):
    def get(self):
        loc_id, date_str = request.args.get('location_id'), request.args.get('date')
        if not loc_id or not date_str:
            flash('缺少必要參數。', 'danger')
            return redirect(url_for('report.query', report_type='daily_settlement_query'))
        loc = Location.query.get_or_404(loc_id)
        try: d = date.fromisoformat(date_str)
        except ValueError: flash('無效日期', 'danger'); return redirect(url_for('report.query', report_type='daily_settlement_query'))
        if BusinessDay.query.filter_by(location_id=loc.id, date=d).first():
            flash('此營業日已存在。', 'warning')
            return redirect(url_for('report.query', report_type='daily_settlement_query'))
        return render_template('admin/force_close_day.html', location=loc, today_date=d.strftime("%Y-%m-%d"), denominations=[1000, 500, 200, 100, 50, 10, 5, 1], form=CloseDayForm(), is_new_entry=True)

    def post(self):
        loc_id, date_str = request.args.get('location_id'), request.args.get('date')
        loc = Location.query.get_or_404(loc_id)
        d = date.fromisoformat(date_str)
        form = CloseDayForm()
        if form.validate_on_submit():
            try:
                total, breakdown = 0, {}
                for d_val in [1000, 500, 200, 100, 50, 10, 5, 1]:
                    count = request.form.get(f"count_{d_val}", 0, type=int)
                    total += count * d_val
                    breakdown[d_val] = count
                new_bd = BusinessDay(date=d, location=loc, opening_cash=0.0, closing_cash=total, cash_breakdown=json.dumps(breakdown), status="CLOSED")
                db.session.add(new_bd)
                db.session.commit()
                flash(f"已補登 {d.strftime('%Y-%m-%d')} 日結。", "success")
                return redirect(url_for('cashier.daily_report', location_slug=loc.slug, date=d.isoformat()))
            except Exception as e:
                db.session.rollback()
                flash(f"錯誤：{e}", "danger")
        return self.get()

class ForceCloseQueryView(AdminBaseView):
    def get(self):
        form = ReportQueryForm()
        form.location_id.choices = [('all', '所有據點')] + [(str(l.id), l.name) for l in Location.query.order_by(Location.id).all()]
        results = []
        if request.args:
            form.process(request.args)
            sd, ed, loc_id = request.args.get('start_date'), request.args.get('end_date'), request.args.get('location_id')
            if sd:
                start_date = date.fromisoformat(sd)
                end_date = date.fromisoformat(ed) if ed else date.today()
                query = BusinessDay.query.options(db.joinedload(BusinessDay.location)).filter(BusinessDay.date.between(start_date, end_date))
                if loc_id and loc_id != 'all': query = query.filter(BusinessDay.location_id == loc_id)
                results = query.order_by(BusinessDay.date.desc(), BusinessDay.location_id).all()
        return render_template('admin/force_close_query.html', form=form, results=results)

# ==========================================
# System Settings & Backup Views
# ==========================================
class SystemSettingsView(AdminBaseView):
    def get(self):
        form = GlobalSettingsForm()
        
        form.drive_folder_name.data = SystemSetting.get('drive_folder_name', '5WayHouse_POS_Reports')
        form.sheets_filename_format.data = SystemSetting.get('sheets_filename_format', '{location_name}_{year}_業績')
        
        backup_files_str = SystemSetting.get('instance_backup_files', '["app.db"]')
        try:
            backup_files = json.loads(backup_files_str)
        except json.JSONDecodeError:
            backup_files = ['app.db']
        
        form.backup_db.data = 'app.db' in backup_files
        form.backup_token.data = 'token.json' in backup_files
        form.backup_client_secret.data = 'client_secret.json' in backup_files
        
        form.backup_frequency.data = SystemSetting.get('instance_backup_frequency', 'off')
        form.backup_interval_minutes.data = int(SystemSetting.get('instance_backup_interval_minutes', '60'))

        is_connected = bool(GoogleIntegrationService.get_google_creds(current_app))
        drive_account_email = None
        if is_connected:
            user_info = GoogleIntegrationService.get_drive_user_info(current_app)
            if user_info and 'email' in user_info:
                drive_account_email = user_info['email']

        return render_template("admin/system_settings.html", is_connected=is_connected, form=form, drive_account_email=drive_account_email)

    def post(self):
        form = GlobalSettingsForm()
        if form.validate_on_submit():
            SystemSetting.set('drive_folder_name', form.drive_folder_name.data)
            SystemSetting.set('sheets_filename_format', form.sheets_filename_format.data)

            backup_files = []
            if form.backup_db.data: backup_files.append('app.db')
            if form.backup_token.data: backup_files.append('token.json')
            if form.backup_client_secret.data: backup_files.append('client_secret.json')
            SystemSetting.set('instance_backup_files', json.dumps(backup_files))
            
            SystemSetting.set('instance_backup_frequency', form.backup_frequency.data)
            SystemSetting.set('instance_backup_interval_minutes', str(form.backup_interval_minutes.data) if form.backup_interval_minutes.data else '60')

            flash('系統全域設定與備份細節已儲存！', 'success')
            return redirect(url_for('admin.system_settings'))
        return self.get()

class RebuildBackupView(AdminSystemView):
    def post(self):
        unclosed = BusinessDay.query.filter(BusinessDay.status.in_(['OPEN', 'PENDING_REPORT'])).all()
        if unclosed:
            reasons = [f"{loc.location.name} ({'正在營業中' if loc.status == 'OPEN' else '報表待確認'})" for loc in unclosed]
            flash(f"備份失敗：因為以下據點尚未完成日結: {', '.join(reasons)}", "danger")
            return redirect(url_for('admin.system_settings'))

        current_app.task_queue.enqueue('app.services.google_service.GoogleIntegrationService.rebuild_backup_task', args=(request.form.get('overwrite') == 'on',), job_timeout='30m')
        flash('已成功提交完整備份請求！備份將在背景執行，請稍後至 Google Drive 查閱結果。', 'info')
        return redirect(url_for('admin.system_settings'))

class ManualInstanceBackupView(AdminSystemView):
    def post(self):
        try:
            current_app.task_queue.enqueue('app.services.backup_service.BackupService.backup_instance_to_drive', job_timeout='10m')
            flash('已成功提交手動備份請求！備份將在背景執行，請稍後至 Google Drive 查閱結果。', 'info')
        except Exception as e:
            flash(f'手動備份失敗：{e}', 'danger')
            current_app.logger.error(f'手動備份失敗: {e}')
        return redirect(url_for('admin.system_settings'))

# ==========================================
# Route Registrations
# ==========================================
bp.add_url_rule('/locations', endpoint='list_locations', methods=['GET'], view_func=LocationListView.as_view('list_locations'))
bp.add_url_rule('/locations/add', endpoint='add_location', methods=['GET', 'POST'], view_func=LocationAddView.as_view('add_location'))
bp.add_url_rule('/locations/<int:location_id>/edit', endpoint='edit_location', methods=['GET', 'POST'], view_func=LocationEditView.as_view('edit_location'))
bp.add_url_rule('/locations/<int:location_id>/delete', endpoint='delete_location', methods=['POST'], view_func=LocationDeleteView.as_view('delete_location'))

bp.add_url_rule('/locations/<int:location_id>/categories', endpoint='list_categories', methods=['GET', 'POST'], view_func=CategoryListView.as_view('list_categories'))
bp.add_url_rule('/locations/<int:location_id>/categories/add', endpoint='add_category', methods=['POST'], view_func=CategoryAddView.as_view('add_category'))
bp.add_url_rule('/categories/<int:category_id>/edit', endpoint='edit_category', methods=['POST'], view_func=CategoryEditView.as_view('edit_category'))
bp.add_url_rule('/categories/<int:category_id>/delete', endpoint='delete_category', methods=['POST'], view_func=CategoryDeleteView.as_view('delete_category'))

bp.add_url_rule('/users', endpoint='list_users', methods=['GET'], view_func=UserListView.as_view('list_users'))
bp.add_url_rule('/users/add', endpoint='add_user', methods=['GET', 'POST'], view_func=UserAddView.as_view('add_user'))
bp.add_url_rule('/users/<int:user_id>/edit', endpoint='edit_user', methods=['GET', 'POST'], view_func=UserEditView.as_view('edit_user'))
bp.add_url_rule('/users/<int:user_id>/delete', endpoint='delete_user', methods=['POST'], view_func=UserDeleteView.as_view('delete_user'))

bp.add_url_rule('/roles', endpoint='list_roles', methods=['GET'], view_func=RoleListView.as_view('list_roles'))
bp.add_url_rule('/roles/add', endpoint='add_role', methods=['GET', 'POST'], view_func=RoleAddView.as_view('add_role'))
bp.add_url_rule('/roles/<int:role_id>/edit', endpoint='edit_role', methods=['GET', 'POST'], view_func=RoleEditView.as_view('edit_role'))
bp.add_url_rule('/roles/<int:role_id>/delete', endpoint='delete_role', methods=['POST'], view_func=RoleDeleteView.as_view('delete_role'))

bp.add_url_rule('/force_close_day/<int:business_day_id>', endpoint='force_close_day', methods=['GET', 'POST'], view_func=ForceCloseDayView.as_view('force_close_day'))
bp.add_url_rule('/force_close_day/new', endpoint='new_force_close_day', methods=['GET', 'POST'], view_func=NewForceCloseDayView.as_view('new_force_close_day'))
bp.add_url_rule('/force_close_query', endpoint='force_close_query', methods=['GET'], view_func=ForceCloseQueryView.as_view('force_close_query'))

bp.add_url_rule('/system_settings', endpoint='system_settings', methods=['GET', 'POST'], view_func=SystemSettingsView.as_view('system_settings'))
bp.add_url_rule('/system_settings/rebuild_backup', endpoint='rebuild_backup', methods=['POST'], view_func=RebuildBackupView.as_view('rebuild_backup'))
bp.add_url_rule('/system_settings/manual_instance_backup', endpoint='manual_instance_backup', methods=['POST'], view_func=ManualInstanceBackupView.as_view('manual_instance_backup'))