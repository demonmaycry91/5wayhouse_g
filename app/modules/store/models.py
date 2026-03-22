from app.core.extensions import db
import json

class Location(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    slug = db.Column(db.String(50), unique=True, nullable=False, index=True)
    business_days = db.relationship('BusinessDay', back_populates='location', lazy=True, cascade="all, delete-orphan")
    categories = db.relationship('Category', back_populates='location', lazy=True, cascade="all, delete-orphan")

    def __repr__(self):
        return f'<Location {self.name}>'

class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    color = db.Column(db.String(7), nullable=False, default='#cccccc')
    location_id = db.Column(db.Integer, db.ForeignKey('location.id'), nullable=False)
    category_type = db.Column(db.String(30), nullable=False, default='product', server_default='product')
    discount_rules = db.Column(db.Text, nullable=True)

    location = db.relationship('Location', back_populates='categories')
    items = db.relationship('TransactionItem', back_populates='category', lazy=True)

    def get_rules(self):
        if self.discount_rules:
            try:
                return json.loads(self.discount_rules)
            except json.JSONDecodeError:
                return {}
        return {}

    def set_rules(self, rules_dict):
        self.discount_rules = json.dumps(rules_dict)

    def __repr__(self):
        return f'<Category {self.name}>'
