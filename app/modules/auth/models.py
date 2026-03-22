# app/modules/auth/models.py
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app.core.extensions import db

roles_users = db.Table('roles_users',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('role_id', db.Integer, db.ForeignKey('role.id'), primary_key=True)
)

roles_locations = db.Table('roles_locations',
    db.Column('role_id', db.Integer, db.ForeignKey('role.id'), primary_key=True),
    db.Column('location_id', db.Integer, db.ForeignKey('location.id'), primary_key=True)
)

PERMISSION_STRUCTURE = {
    '營運功能模組 (POS & Ops)': {
        'pos_operate_cashier': '據點收銀台操作 (開帳/收銀/結帳)',
        'pos_settings': 'POS 端運營環境設定',
    },
    '報表與財務模組 (Reports & Finance)': {
        'report_view_daily': '查閱各據點每日報表',
        'report_edit_daily': '各據點當日結算與補登日結',
        'report_consolidated': '合併報表總結算',
        'report_ocr_verify': '銀行存款收據 OCR 驗證',
    },
    '系統管理後台 (System Admin)': {
        'admin_users': '使用者與角色管理',
        'admin_locations': '據點與商品類別管理',
        'admin_system': '系統全域設定與雲端備份配置',
    },
    '下一階段模組 (Future Phases)': {
        'access_warehouse': '存取倉庫物流管理系統',
        'access_workshop': '存取工坊物資登錄系統',
        'access_accommodation': '存取住宿時段登錄系統',
        'access_volunteer': '存取志工與活動管理系統',
    }
}

class Role(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), unique=True, nullable=False)
    permissions = db.Column(db.Text, nullable=True)
    
    users = db.relationship('User', secondary=roles_users, back_populates='roles')
    locations = db.relationship('Location', secondary=roles_locations, backref=db.backref('roles', lazy='dynamic'))

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
        # Admin bypasses all checks
        if self.has_role('Admin'):
            return True
        for role in self.roles:
            perms = [p.lower().strip() for p in role.get_permissions()]
            if permission_name.lower().strip() in perms:
                return True
        return False
        
    def can_access_location(self, location_id_or_slug):
        # Admin bypasses all specific location locks
        if self.has_role('Admin'):
            return True
        for role in self.roles:
            for loc in role.locations:
                if str(loc.id) == str(location_id_or_slug) or loc.slug == location_id_or_slug:
                    return True
        return False

    def __repr__(self):
        return f'<User {self.username}>'
