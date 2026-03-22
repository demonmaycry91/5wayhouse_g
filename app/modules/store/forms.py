from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, SelectField, IntegerField
from wtforms.fields import ColorField
from wtforms.validators import DataRequired, Length, Regexp, Optional
from .models import Category

class LocationForm(FlaskForm):
    name = StringField('據點名稱', validators=[DataRequired(message="請輸入据點名稱。"), Length(max=50)])
    slug = StringField('URL Slug', validators=[
        DataRequired(message="請輸入 URL Slug。"), 
        Length(max=50),
        Regexp(r'^[a-z0-9]+(?:-[a-z0-9]+)*$', message='Slug 只能包含小寫英文、數字和連字號 (-)，且不能以連字號開頭或結尾。')
    ])
    submit = SubmitField('儲存')

class CategoryForm(FlaskForm):
    name = StringField('類別名稱', validators=[DataRequired(), Length(1, 50)])
    color = ColorField('按鈕顏色', default='#cccccc', validators=[DataRequired()])
    
    category_type = SelectField(
        '類別類型',
        choices=[
            ('product', '一般商品 (加法)'),
            ('discount_fixed', '固定金額折扣 (減法)'),
            ('discount_percent', '百分比折扣 (乘法)'),
            ('product_discount_percent', '商品打折'),
            ('buy_n_get_m', '買 N 送 M (固定)'),
            ('buy_x_get_x_minus_1', '買 X 送 X-1 (動態)'),
            ('buy_odd_even', '成雙優惠 (奇數件)'),
            ('other_income', '其他收入')
        ],
        validators=[DataRequired()]
    )
    rule_target_category_id = SelectField('目標商品類別', coerce=int, validators=[Optional()])
    rule_buy_n = IntegerField('購買數量 (N)', validators=[Optional()])
    rule_get_m = IntegerField('免費/優惠數量 (M)', validators=[Optional()])

    submit = SubmitField('儲存')

    def __init__(self, location_id, *args, **kwargs):
        super(CategoryForm, self).__init__(*args, **kwargs)
        self.rule_target_category_id.choices = [
            (c.id, c.name) for c in Category.query.filter_by(
                location_id=location_id, category_type='product'
            ).order_by('name').all()
        ]
