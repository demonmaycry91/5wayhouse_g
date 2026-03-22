from app.core.extensions import db
from datetime import datetime, timezone

class BusinessDay(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False)
    
    location_id = db.Column(db.Integer, db.ForeignKey('location.id'), nullable=False)
    location = db.relationship('Location', back_populates='business_days')
    
    location_notes = db.Column(db.String(200), nullable=True)
    status = db.Column(db.String(20), nullable=False, default='NOT_STARTED')
    opening_cash = db.Column(db.Float, nullable=False)
    total_sales = db.Column(db.Float, default=0.0)
    closing_cash = db.Column(db.Float, nullable=True)
    expected_cash = db.Column(db.Float, nullable=True)
    cash_diff = db.Column(db.Float, nullable=True)
    total_items = db.Column(db.Integer, default=0)
    total_transactions = db.Column(db.Integer, default=0)
    cash_breakdown = db.Column(db.Text, nullable=True)
    signature_operator = db.Column(db.Text, nullable=True)
    signature_reviewer = db.Column(db.Text, nullable=True)
    signature_cashier = db.Column(db.Text, nullable=True)
    
    transactions = db.relationship('Transaction', backref='business_day', lazy=True, cascade="all, delete-orphan")
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    next_day_opening_cash = db.Column(db.Float, nullable=True)

    def __repr__(self):
        return f'<BusinessDay {self.date} - Location ID: {self.location_id}>'

class DailySettlement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False, unique=True)
    total_deposit = db.Column(db.Float, nullable=True)
    total_next_day_opening_cash = db.Column(db.Float, nullable=True)
    remarks = db.Column(db.Text, nullable=True) # Stored as JSON

    # 銀行存款收據驗證欄位
    deposit_receipt_path = db.Column(db.String(512), nullable=True) # 收據圖片路徑
    deposit_ocr_amount = db.Column(db.Float, nullable=True)         # OCR 讀取的存款金額
    deposit_verified = db.Column(db.Boolean, nullable=True, default=None) # None=未驗證, True=已核實, False=有差異
    
    # 紀錄是哪個帳號上傳的
    deposit_uploader_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    deposit_uploader = db.relationship('User', foreign_keys=[deposit_uploader_id])
