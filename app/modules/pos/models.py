from app.core.extensions import db
from datetime import datetime

class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    amount = db.Column(db.Float, nullable=False)
    item_count = db.Column(db.Integer, nullable=False)
    business_day_id = db.Column(db.Integer, db.ForeignKey('business_day.id'), nullable=False)
    items = db.relationship('TransactionItem', back_populates='transaction', lazy=True, cascade="all, delete-orphan")

    cash_received = db.Column(db.Float, nullable=True)
    change_given = db.Column(db.Float, nullable=True)
    discounts = db.Column(db.Text, nullable=True)

    def __repr__(self):
        return f'<Transaction {self.id} - Amount: {self.amount}>'

class TransactionItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    price = db.Column(db.Float, nullable=False)
    transaction_id = db.Column(db.Integer, db.ForeignKey('transaction.id'), nullable=False)
    transaction = db.relationship('Transaction', back_populates='items')
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=False)
    category = db.relationship('Category', back_populates='items')

    def __repr__(self):
        return f'<TransactionItem {self.id} - Price: {self.price}>'
