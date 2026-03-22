# app/routes/workshop_routes.py
from flask import render_template, abort, Blueprint
from flask.views import MethodView
from flask_login import current_user


from app.core.decorators import require_module_permission

bp = Blueprint('workshop', __name__, url_prefix='/workshop')

class DashboardView(MethodView):
    decorators = [require_module_permission('access_workshop')]

    def get(self):
        return render_template('workshop/dashboard.html')


bp.add_url_rule('/dashboard', endpoint='dashboard', view_func=DashboardView.as_view('dashboard'))
