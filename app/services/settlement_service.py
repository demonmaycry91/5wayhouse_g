from sqlalchemy.sql import func
from app.core.extensions import db
from app.modules.daily_ops.models import BusinessDay
from app.modules.pos.models import Transaction, TransactionItem
from app.modules.store.models import Category

class GrandTotal:
    def __init__(self, **entries):
        self.__dict__.update(entries)

FINANCE_ITEMS = [
    ('A', '應有現金',       'A', 'expected_cash_new'),
    ('B', '開店現金',       'B', 'opening_cash'),
    ('C', '手帳營收',       'C', 'total_sales'),
    ('D', '其他現金',       'D', 'other_cash'),
    ('E', '實有現金',       'E', 'closing_cash'),
    ('F', '溢短收',         'F', 'cash_diff_new'),
    ('H', '存款',           'H', 'deposit'),
    ('I', '明日開店現金',   'I', 'next_day_opening_cash'),
]

SALES_ITEMS = [
    ('J', '結單數', 'J', 'total_transactions'),
    ('K', '品項數', 'K', 'total_items'),
]

class SettlementService:
    """合併結算計算服務"""

    @staticmethod
    def compute_other_income(business_day_id: int) -> tuple[float, float]:
        results = db.session.query(
            Category.name, func.sum(TransactionItem.price)
        ).join(TransactionItem.transaction).join(Transaction.business_day).join(
            TransactionItem.category
        ).filter(
            BusinessDay.id == business_day_id,
            Category.category_type == 'other_income'
        ).group_by(Category.name).all()

        donation_total = 0.0
        other_total = 0.0
        for name, total in results:
            if name == '捐款':
                donation_total = total or 0.0
            else:
                other_total += (total or 0.0)
        return donation_total, other_total

    @classmethod
    def compute_grand_total(cls, closed_reports: list, daily_settlement=None) -> GrandTotal:
        for r in closed_reports:
            r.donation_total, r.other_total = cls.compute_other_income(r.id)

        t: dict[str, float] = {}
        t['B'] = sum(r.opening_cash or 0 for r in closed_reports)       
        t['C'] = sum(r.total_sales or 0 for r in closed_reports)         
        t['D'] = sum((r.donation_total + r.other_total) for r in closed_reports) 
        t['E'] = sum(r.closing_cash or 0 for r in closed_reports)        
        t['A'] = t['B'] + t['C'] + t['D']                                
        t['F'] = t['E'] - t['A']                                         
        t['J'] = sum(r.total_transactions or 0 for r in closed_reports)  
        t['K'] = sum(r.total_items or 0 for r in closed_reports)         

        if daily_settlement is not None:
            t['H'] = daily_settlement.total_deposit or 0.0
            t['I'] = daily_settlement.total_next_day_opening_cash or 0.0
        else:
            t['I'] = 0.0
            t['H'] = t['E'] - t['I']

        return GrandTotal(**t)
