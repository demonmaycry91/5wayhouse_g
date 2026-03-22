# app/routes/auth_routes.py
"""
Shared Authentication Blueprint
Routes: /login (GET/POST), /logout (GET)
This is the single entry point for all user authentication regardless of which module they use.
"""
from flask import render_template, request, redirect, url_for, flash, Blueprint, current_app
from flask.views import MethodView
from flask_login import login_user, logout_user, login_required, current_user
from urllib.parse import urlparse, urljoin

from app.core.extensions import limiter
from app.modules.auth.models import User
from app.modules.auth.forms import LoginForm

bp = Blueprint('auth', __name__)

# ==========================================
# Auth Views (OOP)
# ==========================================

class LoginView(MethodView):
    """Shared login page: /login"""
    decorators = [limiter.limit("10 per minute", error_message="登入嘗試次數過多，請稍候再試。")]

    def _safe_next(self, next_page: str | None) -> str | None:
        """Validate the next redirect is same-origin."""
        if not next_page:
            return None
        parsed = urlparse(urljoin(request.host_url, next_page))
        if urlparse(request.host_url).netloc != parsed.netloc:
            return None
        return next_page

    def _default_redirect(self, user: User) -> str:
        """Route user to the correct dashboard based on their role/permissions."""
        if user.has_role('Admin') or user.can('pos_operate_cashier') or user.can('report_view_daily'):
            return url_for('cashier.dashboard')
        elif user.can('access_warehouse'):
            return url_for('warehouse.dashboard')
        elif user.can('access_workshop'):
            return url_for('workshop.dashboard')
        elif user.can('access_accommodation'):
            return url_for('accommodation.dashboard')
        elif user.can('access_volunteer'):
            return url_for('volunteer.dashboard')
        return url_for('main.index')

    def get(self):
        if current_user.is_authenticated:
            next_page = self._safe_next(request.args.get('next'))
            return redirect(next_page or self._default_redirect(current_user))
        return render_template('auth/login.html', form=LoginForm())

    def post(self):
        if current_user.is_authenticated:
            return redirect(self._default_redirect(current_user))

        form = LoginForm()
        if form.validate_on_submit():
            user = User.query.filter_by(username=form.username.data).first()
            if user is None or not user.check_password(form.password.data):
                current_app.logger.warning(
                    "LOGIN_FAILED | username=%s | ip=%s", form.username.data, request.remote_addr
                )
                flash("帳號或密碼錯誤，請重新輸入。", "danger")
                return redirect(url_for('auth.login', next=request.args.get('next', '')))

            login_user(user)
            current_app.logger.info(
                "LOGIN_SUCCESS | user_id=%s | username=%s | ip=%s", user.id, user.username, request.remote_addr
            )

            next_page = self._safe_next(request.args.get('next'))
            return redirect(next_page or self._default_redirect(user))

        return render_template('auth/login.html', form=form)


class LogoutView(MethodView):
    """Shared logout: /logout"""
    decorators = [login_required]

    def get(self):
        current_app.logger.info(
            "LOGOUT | user_id=%s | username=%s | ip=%s", current_user.id, current_user.username, request.remote_addr
        )
        logout_user()
        flash("您已成功登出。", "info")
        return redirect(url_for('auth.login'))


bp.add_url_rule('/login', endpoint='login', view_func=LoginView.as_view('login'))
bp.add_url_rule('/logout', endpoint='logout', view_func=LogoutView.as_view('logout'))
