"""
Phase 2: 志工與活動管理 (Volunteer Module)
預計未來擴充功能：
- 開設與管理多個志工活動
- 登錄志工個人信息與參與紀錄
- 支援設定多種證書模板
- 自動生成該活動志工的感謝狀 / 證明狀 (可能整合 PDFGeneratorService)
"""
from app.core.extensions import db

# class VolunteerActivity(db.Model):
#     __tablename__ = 'volunteer_activities'
#     id = db.Column(db.Integer, primary_key=True)
#     title = db.Column(db.String(200), nullable=False)
#     date_start = db.Column(db.DateTime)
#     certificate_template = db.Column(db.String(200)) # 證書模板格式參考
#     # records = db.relationship('VolunteerRecord', backref='activity')

# class Volunteer(db.Model):
#     __tablename__ = 'volunteers'
#     # ...
