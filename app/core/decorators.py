from functools import wraps
from flask import abort
from flask_login import current_user

def admin_required(f):
    """
    一個裝飾器，用來確保只有具備 'Admin' 角色的使用者才能存取某個路由。
    如果使用者未登入或不具備 'Admin' 角色，將會回傳 403 Forbidden 錯誤。
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.has_role('Admin'):
            abort(403)  # Forbidden
        return f(*args, **kwargs)
    return decorated_function

def require_module_permission(permission_name):
    """
    Ensure the user has the required permission for a module.
    If not authenticated, it renders a login prompt inline instead of a hard redirect.
    If authenticated but lacking permission, it aborts with 403.
    """
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            from flask import request, render_template
            if not current_user.is_authenticated:
                return render_template('partials/login_required.html', next=request.path)
            if not (current_user.has_role('Admin') or current_user.can(permission_name)):
                abort(403)
            return f(*args, **kwargs)
        return decorated
    return decorator
