from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from sqlalchemy import MetaData

convention = {
    "ix": 'ix_%(column_0_label)s',
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s"
}

metadata = MetaData(naming_convention=convention)
db = SQLAlchemy(metadata=metadata)
migrate = Migrate()
login_manager = LoginManager()
csrf = CSRFProtect()

# 速率限制器（預設無全域限制，各路由獨立設定）
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[],
    storage_uri="memory://"   # 可改為 Redis URI 以在多 Worker 間共享
)

# 由於登入視圖會搬到 auth module，這裡可能需要延後設定或稍後再更新
login_manager.login_view = 'auth.login'
login_manager.login_message = '請先登入以存取此頁面。'
login_manager.login_message_category = 'warning'


