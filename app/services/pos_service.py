from datetime import date
from sqlalchemy import func
from app.core.extensions import db
from app.modules.store.models import Location, Category
from app.modules.daily_ops.models import BusinessDay
from app.modules.pos.models import Transaction, TransactionItem

class POSService:
    @staticmethod
    def record_transaction(location_slug, items, cash_received, change_given):
        """處理單筆 POS 交易進資料庫，並同步更新該日指標"""
        if not items:
            return False, "交易內容不可為空"

        location = Location.query.filter_by(slug=location_slug).first()
        business_day = BusinessDay.query.filter_by(date=date.today(), location_id=location.id, status="OPEN").first()
        
        if not business_day:
            return False, "找不到對應的營業中紀錄"

        total_amount = sum(item['price'] for item in items)
        total_sales_amount = 0
        total_items_count = 0
        
        for item in items:
            category = Category.query.get(item['category_id'])
            if category and category.category_type in ['product', 'discount_fixed', 'discount_percent', 'buy_n_get_m', 'buy_x_get_x_minus_1', 'buy_odd_even']:
                total_sales_amount += item['price']
            if category and category.category_type == 'product':
                total_items_count += 1
        
        new_tx = Transaction(amount=total_amount, item_count=len(items), business_day_id=business_day.id, cash_received=cash_received, change_given=change_given)
        db.session.add(new_tx)
        
        for item in items:
            db.session.add(TransactionItem(price=item['price'], category_id=item['category_id'], transaction=new_tx))

        business_day.total_sales = (business_day.total_sales or 0) + total_sales_amount
        business_day.total_items = (business_day.total_items or 0) + total_items_count
        business_day.total_transactions = (business_day.total_transactions or 0) + 1
        db.session.commit()
        
        other_incomes = db.session.query(Category.name, func.sum(TransactionItem.price)) \
            .join(TransactionItem.transaction).join(Transaction.business_day).join(TransactionItem.category) \
            .filter(BusinessDay.id == business_day.id, Category.category_type == 'other_income') \
            .group_by(Category.name).all()
            
        donation_total = sum(total for name, total in other_incomes if name == '捐款')
        other_total = sum(total for name, total in other_incomes if name != '捐款')
        
        return True, {
            "total_sales": business_day.total_sales,
            "donation_total": donation_total,
            "other_total": other_total
        }

    @staticmethod
    def calculate_daily_totals(business_day_id):
        """計算指定營業日的各項交易總額，並返回 (sales_total, other_income_total)"""
        sales_total = db.session.query(func.sum(TransactionItem.price)).join(Transaction.items).join(TransactionItem.category).filter(
            Transaction.business_day_id == business_day_id,
            Category.category_type.in_(['product', 'discount_fixed', 'discount_percent', 'buy_n_get_m', 'buy_x_get_x_minus_1', 'buy_odd_even'])
        ).scalar() or 0
        
        other_income_total = db.session.query(func.sum(TransactionItem.price)).join(TransactionItem.transaction).join(Transaction.business_day).join(TransactionItem.category).filter(
            BusinessDay.id == business_day_id, Category.category_type == 'other_income'
        ).scalar() or 0
        
        return sales_total, other_income_total
