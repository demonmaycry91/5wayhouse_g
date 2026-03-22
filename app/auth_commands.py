import click
from flask.cli import with_appcontext
from app.core.extensions import db
from app.modules.auth.models import User, Role

@click.group(name='auth', help="使用者驗證相關指令")
def auth_cli():
    pass

@auth_cli.command("create-user")
@click.argument("username")
@click.argument("password")
@click.option('--role', default='Cashier', help="為使用者指派的角色 (例如: Admin, Cashier)")
@with_appcontext
def create_user(username, password, role):
    """建立一個新的使用者帳號"""
    if User.query.filter_by(username=username).first():
        click.echo(f"錯誤：使用者 '{username}' 已經存在。")
        return

    user_role = Role.query.filter_by(name=role).first()
    if not user_role:
        click.echo(f"錯誤：角色 '{role}' 不存在。請先執行 'flask auth init-roles'。")
        return

    new_user = User(username=username)
    new_user.set_password(password)
    new_user.roles.append(user_role) # 指派角色
    db.session.add(new_user)
    db.session.commit()
    click.echo(f"成功建立使用者：'{username}'，並指派角色：'{role}'。")

@auth_cli.command("reset-password")
@click.argument("username")
@click.argument("new_password")
@with_appcontext
def reset_password(username, new_password):
    """重設指定使用者的密碼"""
    user = User.query.filter_by(username=username).first()
    if user is None:
        click.echo(f"錯誤：找不到使用者 '{username}'。")
        return
    user.set_password(new_password)
    db.session.commit()
    click.echo(f"使用者 '{username}' 的密碼已成功重設。")

# --- 新增：初始化角色的指令 ---
@auth_cli.command("init-roles")
@with_appcontext
def init_roles():
    """在資料庫中建立預設的角色與權限 (Admin, Manager, Cashier)"""
    from app.modules.auth.models import PERMISSION_STRUCTURE
    import click
    all_perms = []
    for group, perms in PERMISSION_STRUCTURE.items():
        all_perms.extend(perms.keys())
    
    default_roles = {
        'Admin': all_perms,
        'Manager': ['admin_locations', 'admin_users', 'report_view_daily', 'report_consolidated'],
        'Cashier': ['pos_operate_cashier'],
        'Logistic': ['access_warehouse'],
        'Workshop': ['access_workshop'],
        'Reception': ['access_accommodation'],
        'Coordinator': ['access_volunteer']
    }
    
    for r_name, r_perms in default_roles.items():
        role = Role.query.filter_by(name=r_name).first()
        if not role:
            role = Role(name=r_name, permissions=','.join(r_perms))
            db.session.add(role)
            click.echo(f"成功建立角色：'{r_name}' 並自動分配權限。")
        else:
            role.permissions = ','.join(r_perms)
            click.echo(f"已更新角色：'{r_name}' 的預設權限配置。")
            
    db.session.commit()
    click.echo("所有預設角色初始化完成。")

@auth_cli.command("seed-users")
@click.option('--password', default='123456', help="預設測試密碼")
@with_appcontext
def seed_users(password):
    """建立各個子系統功能的預設測試專職帳號"""
    demo_accounts = [
        ('admin', 'Admin'),
        ('cashier', 'Cashier'),
        ('logistician', 'Logistic'),
        ('artisan', 'Workshop'),
        ('reception', 'Reception'),
        ('coordinator', 'Coordinator')
    ]
    
    for username, role_name in demo_accounts:
        user = User.query.filter_by(username=username).first()
        if not user:
            role = Role.query.filter_by(name=role_name).first()
            if not role:
                click.echo(f"警告：角色 '{role_name}' 不存在，跳過建立 '{username}'。請先執行 init-roles。")
                continue
                
            new_user = User(username=username)
            new_user.set_password(password)
            new_user.roles.append(role)
            db.session.add(new_user)
            click.echo(f"已建立預設帳號：{username} (指派職務角色: {role_name})")
        else:
            click.echo(f"預設帳號 '{username}' 已存在，略過。")
            
    db.session.commit()
    click.echo("✅ Phase 2 & 現存子系統的預設測試帳號佈署完成！")


def init_app(app):
    """在 App 中註冊指令"""
    app.cli.add_command(auth_cli)
