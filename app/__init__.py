import logging
from logging.handlers import RotatingFileHandler
from flask import Flask
import os
from dotenv import load_dotenv
from redis import Redis
import rq
import json

from config import config as app_config
from app.core.extensions import db, migrate, login_manager, csrf, limiter

load_dotenv()


def _configure_logging(app: Flask):
    """設定應用程式的日誌系統（Console + 滾動檔案日誌）。"""
    log_level = logging.DEBUG if app.debug else logging.INFO
    formatter = logging.Formatter(
        '[%(asctime)s] %(levelname)s in %(module)s: %(message)s'
    )

    # Console handler
    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(log_level)
    stream_handler.setFormatter(formatter)

    # Rotating file handler (最多 10 MB × 5 個備份)
    logs_dir = os.path.join(app.instance_path, 'logs')
    os.makedirs(logs_dir, exist_ok=True)
    file_handler = RotatingFileHandler(
        os.path.join(logs_dir, 'app.log'),
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(log_level)
    file_handler.setFormatter(formatter)

    app.logger.setLevel(log_level)
    app.logger.addHandler(stream_handler)
    app.logger.addHandler(file_handler)

    app.logger.info("Application logging configured.")



def create_app(config_name=None):
    if config_name is None:
        config_name = os.getenv('FLASK_ENV', 'default')

    app = Flask(__name__, instance_relative_config=True)
    
    # 載入設定檔
    app.config.from_object(app_config[config_name]())
    
    # 強制安全 Cookie 設定
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    
    app.redis = Redis.from_url(app.config['REDIS_URL'])
    app.task_queue = rq.Queue('cashier-tasks', connection=app.redis)

    csrf.init_app(app)
    db.init_app(app)
    migrate.init_app(app, db, render_as_batch=True)
    login_manager.init_app(app)
    limiter.init_app(app)
    _configure_logging(app)



    def from_json_filter(value):
        if value:
            return json.loads(value)
        return {}
    app.jinja_env.filters['from_json'] = from_json_filter

    from app.routes import main_routes, auth_routes, cashier_routes, report_routes, admin_routes, \
                           google_routes, ocr_routes, warehouse_routes, \
                           workshop_routes, accommodation_routes, volunteer_routes
    app.register_blueprint(main_routes.bp)
    app.register_blueprint(auth_routes.bp)
    app.register_blueprint(ocr_routes.bp)
    app.register_blueprint(cashier_routes.bp)
    app.register_blueprint(google_routes.bp)
    app.register_blueprint(admin_routes.bp)
    app.register_blueprint(report_routes.bp)
    app.register_blueprint(warehouse_routes.bp)
    app.register_blueprint(workshop_routes.bp)
    app.register_blueprint(accommodation_routes.bp)
    app.register_blueprint(volunteer_routes.bp)

    from app.modules.auth import models
    from app.modules.store import models
    from app.modules.daily_ops import models
    from app.modules.pos import models
    from app.modules.system import models
    from . import auth_commands
    from . import backup_commands
    auth_commands.init_app(app)
    backup_commands.init_app(app)

    # ── HTTP 安全標頭 ─────────────────────────────────────────────────────
    @app.after_request
    def set_security_headers(response):
        """每個 Response 自動加入安全標頭。"""
        # 防止 Clickjacking（禁止嵌入 iframe）
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        # 防止瀏覽器 MIME 類型嗅探
        response.headers['X-Content-Type-Options'] = 'nosniff'
        # 舊版瀏覽器 XSS 過濾
        response.headers['X-XSS-Protection'] = '1; mode=block'
        # 控制 Referer 標頭洩露
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        # 強制使用 HTTPS (HSTS)
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        # 限制瀏覽器功能（攝影機、麥克風等）
        response.headers['Permissions-Policy'] = (
            'geolocation=(), microphone=(), camera=()'
        )
        # Content Security Policy（允許同站資源、Bootstrap CDN、inline style）
        response.headers['Content-Security-Policy'] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            "img-src 'self' data: blob:; "
            "connect-src 'self';"
        )
        return response

    # ── 自訂錯誤頁面 ───────────────────────────────────────────────────────
    @app.errorhandler(404)
    def not_found_error(error):
        from flask import render_template
        return render_template('errors/404.html'), 404

    @app.errorhandler(413)
    def request_entity_too_large(error):
        from flask import render_template
        return render_template('errors/413.html'), 413

    @app.errorhandler(429)
    def rate_limit_error(error):
        from flask import render_template
        return render_template('errors/429.html'), 429

    @app.errorhandler(500)
    def internal_error(error):
        from app.core.extensions import db
        db.session.rollback()
        app.logger.error("500 Internal Server Error: %s", error, exc_info=True)
        from flask import render_template
        return render_template('errors/500.html'), 500

    return app