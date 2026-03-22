"""
Phase 2: 倉庫物流管理模組 (Warehouse Module)
預計未來擴充功能：
- 貨物分類後進入倉庫的登記
- 倉庫出貨到各個實體店鋪的紀錄與盤點
"""
from app.core.extensions import db

# class WarehouseItem(db.Model):
#     __tablename__ = 'warehouse_items'
#     id = db.Column(db.Integer, primary_key=True)
#     name = db.Column(db.String(100), nullable=False)
#     stock_quantity = db.Column(db.Integer, default=0)
#     # ... 其他欄位（如入庫時間、出庫紀錄關聯等）
