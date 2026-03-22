from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app.core.extensions import db

roles_users = db.Table('roles_users',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('role_id', db.Integer, db.ForeignKey('role.id'), primary_key=True)
)

class Permission:
    MANAGE_USERS = 'manage_users'
    MANAGE_ROLES = 'manage_roles'
    MANAGE_LOCATIONS = 'manage_locations'
    VIEW_REPORTS = 'view_reports'
    OPERATE_POS = 'operate_pos'
    SYSTEM_SETTINGS = 'system_settings'

PERMISSION_DESCRIPTIONS = {
    'MANAGE_USERS': '新增、編輯與刪除使用者帳號',
    'MANAGE_ROLES': '設定系統角色與分配各項權限',
    'MANAGE_LOCATIONS': '新增、編輯營業據點與管理商品類別、打折規則',
    'VIEW_REPORTS': '檢視營運報表、執行合併日結與上傳/驗證銀行存款收據',
    'OPERATE_POS': '登入據點收銀台、執行日常開帳、收銀結帳與單點日結盤點',
    'SYSTEM_SETTINGS': '設定系統進階選項（如修改密碼、Google Drive 雲端同步設定）'
}

class Role(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), unique=True, nullable=False)
    permissions = db.Column(db.Text, nullable=True)
    users = db.relationship('User', secondary=roles_users, back_populates='roles')

    def __repr__(self):
        return f'<Role {self.name}>'
        
    def get_permissions(self):
        if self.permissions:
            return self.permissions.split(',')
        return []

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=True)
    google_id = db.Column(db.String(120), unique=True, nullable=True, index=True)
    password_hash = db.Column(db.String(200), nullable=True)
    roles = db.relationship('Role', secondary=roles_users, back_populates='users', lazy='dynamic')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)
        
    def has_role(self, role_name):
        return self.roles.filter_by(name=role_name).first() is not None

    def can(self, permission_name):
        for role in self.roles:
            if permission_name in role.get_permissions():
                return True
        return False

    def __repr__(self):
        return f'<User {self.username}>'
