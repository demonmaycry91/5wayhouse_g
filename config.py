import os

class Config:
    """Base configuration class."""
    # 安全性設定
    # 這裡強制生產環境必須提供 SECRET_KEY，否則報錯，防止預設字串外洩風險。
    # 為了開發方便，如果是在 DevelopmentConfig 才會給預設值。
    SECRET_KEY = os.environ.get('SECRET_KEY')
    if not SECRET_KEY:
        raise ValueError("No SECRET_KEY set for Flask application. You must set it in .env or environment variables.")
        
    # Cookie & Session 安全設定
    SESSION_PERMANENT = False
    SESSION_COOKIE_SECURE = True  # 僅在 HTTPS 傳輸 Cookie
    SESSION_COOKIE_HTTPONLY = True # 防止 JavaScript 讀取 Cookie
    SESSION_COOKIE_SAMESITE = 'Lax' # 防止 CSRF，如果是完全不同的站點發起請求則不帶 Cookie
    SESSION_COOKIE_NAME = '5wayhouse_session'  # 避免暴露 Flask 預設名稱

    # Session 有效期（即使 SESSION_PERMANENT=False，也限制 8 小時內活動）
    import datetime
    PERMANENT_SESSION_LIFETIME = datetime.timedelta(hours=8)

    # 全域上傳大小限制（20 MB — 防止 DoS 攻擊）
    MAX_CONTENT_LENGTH = 20 * 1024 * 1024
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Redis & RQ 設定
    REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')

class DevelopmentConfig(Config):
    """Development configuration."""
    DEBUG = True
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-fallback-secret-key-only-for-local')
    
    # 在本地開發時關閉 Secure cookie (因為通常沒有 HTTPS)
    SESSION_COOKIE_SECURE = False
    
    @property
    def SQLALCHEMY_DATABASE_URI(self):
        # 如果有 explicitly set DATABASE_URL (例如開發時用了 local postgres)，就用它
        db_url = os.environ.get('DATABASE_URL')
        if db_url:
            return db_url
        
        # 否則使用 instance 內的 sqlite
        # 這裡的 base_dir 需要動態計算
        base_dir = os.path.abspath(os.path.dirname(__file__))
        instance_path = os.path.join(base_dir, 'instance')
        os.makedirs(instance_path, exist_ok=True)
        return f'sqlite:///{os.path.join(instance_path, "app.db")}'

class ProductionConfig(Config):
    """Production configuration."""
    DEBUG = False
    
    @property
    def SQLALCHEMY_DATABASE_URI(self):
        db_url = os.environ.get('DATABASE_URL')
        if not db_url:
            # 即便是 Production，如果使用者還沒設定 PostgreSQL，暫時退回到本機 SQLite 確保運作
            base_dir = os.path.abspath(os.path.dirname(__file__))
            instance_path = os.path.join(base_dir, 'instance')
            return f'sqlite:///{os.path.join(instance_path, "app.db")}'
        return db_url

class TestingConfig(Config):
    """Testing configuration."""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:' # 測試用記憶體 DB
    WTF_CSRF_ENABLED = False # 測試時通常關閉 CSRF
    SECRET_KEY = 'test-secret'
    SESSION_COOKIE_SECURE = False

config = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}
