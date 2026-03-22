# app/routes/accommodation_routes.py
from flask import render_template, abort, Blueprint
from flask.views import MethodView
from flask_login import login_required, current_user

bp = Blueprint('accommodation', __name__, url_prefix='/accommodation')


def require_accommodation_access(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated:
            abort(401)
        if not (current_user.has_role('Admin') or current_user.can('access_accommodation')):
            abort(403)
        return f(*args, **kwargs)
    return decorated


class DashboardView(MethodView):
    decorators = [login_required, require_accommodation_access]

    def get(self):
        return render_template('accommodation/dashboard.html')


bp.add_url_rule('/dashboard', endpoint='dashboard', view_func=DashboardView.as_view('dashboard'))
