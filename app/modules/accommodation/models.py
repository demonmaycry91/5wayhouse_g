"""
Phase 2: 住宿登錄系統 (Accommodation Module)
預計未來擴充功能：
- 設定多個住宿地點
- 管理每個住宿地點的房間（數量、類型、可容納人數）
- 登記與查詢訪客/員工的住宿時段
"""
from app.core.extensions import db

# class AccommodationLocation(db.Model):
#     __tablename__ = 'accommodation_locations'
#     id = db.Column(db.Integer, primary_key=True)
#     name = db.Column(db.String(100), nullable=False)
#     address = db.Column(db.String(200))
#     # rooms = db.relationship('Room', backref='location')

# class Room(db.Model):
#     __tablename__ = 'rooms'
#     id = db.Column(db.Integer, primary_key=True)
#     location_id = db.Column(db.Integer, db.ForeignKey('accommodation_locations.id'))
#     room_type = db.Column(db.String(50))
#     capacity = db.Column(db.Integer, default=1)
#     # ... 住宿時段紀錄關聯
