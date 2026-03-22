# app/routes/workshop_routes.py
from flask import render_template, abort, Blueprint
from flask.views import MethodView
from flask_login import login_required, current_user

bp = Blueprint('workshop', __name__, url_prefix='/workshop')


def require_workshop_access(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated:
            abort(401)
        if not (current_user.has_role('Admin') or current_user.can('access_workshop')):
            abort(403)
        return f(*args, **kwargs)
    return decorated


class DashboardView(MethodView):
    decorators = [login_required, require_workshop_access]

    def get(self):
        return render_template('workshop/dashboard.html')


bp.add_url_rule('/dashboard', endpoint='dashboard', view_func=DashboardView.as_view('dashboard'))
