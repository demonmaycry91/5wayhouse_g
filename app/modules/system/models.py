from app.core.extensions import db

class SystemSetting(db.Model):
    __tablename__ = 'system_setting'
    key = db.Column(db.String(50), primary_key=True)
    value = db.Column(db.String(200), nullable=True)

    @staticmethod
    def get(key, default=None):
        from flask import g
        if not hasattr(g, 'system_settings') or g.system_settings is None:
            g.system_settings = {s.key: s.value for s in SystemSetting.query.all()}
        return g.system_settings.get(key, default)

    @staticmethod
    def set(key, value):
        from flask import g
        setting = SystemSetting.query.filter_by(key=key).first()
        if setting:
            setting.value = value
        else:
            setting = SystemSetting(key=key, value=value)
            db.session.add(setting)
        db.session.commit()
        if hasattr(g, 'system_settings'):
            g.system_settings = None
