"""
Phase 2: 工坊登記系統 (Workshop Module)
預計未來擴充功能：
- 捐贈物資到達時的箱數登記
- 開箱驗收並使用 OCR 掃描寄件單據
- 登記與歸檔寄件人資訊、內容物清單
"""
from app.core.extensions import db

# class DonationBox(db.Model):
#     __tablename__ = 'donation_boxes'
#     id = db.Column(db.Integer, primary_key=True)
#     tracking_number = db.Column(db.String(100), unique=True)
#     sender_name = db.Column(db.String(100))
#     sender_info_raw = db.Column(db.Text) # 用於儲存 OCR 辨識出的原始文字
#     # ... 其他欄位（如開箱狀態、照片路徑等）
