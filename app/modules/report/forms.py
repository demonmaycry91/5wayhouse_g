from flask_wtf import FlaskForm
from wtforms import SelectField, DateField, SubmitField
from wtforms.validators import DataRequired, Optional
from datetime import date
from ..store.models import Location

class ReportQueryForm(FlaskForm):
    report_type = SelectField('報表類型', choices=[
        ('daily_summary', '各據點每日報表'),
        ('daily_cash_summary', '各據點當日結算'),
        ('daily_cash_check', '各據點現金盤點'),
        ('transaction_log', '各據點交易細節'),
        ('daily_settlement_query', '各據點日結查詢'),
        ('combined_summary_final', '合併報表總結 (現金核對)'),
        ('product_mix', '產品類別銷售分析'),
        ('sales_trend', '銷售趨勢報告'),
        ('peak_hours', '時段銷售分析'),
        ('periodic_performance', '週期性業績分析')
    ], validators=[DataRequired()])
    
    location_id = SelectField('據點', coerce=str, validators=[Optional()])
    status = SelectField('狀態', choices=[
        ('all', '所有狀態'),
        ('open', '營業中'),
        ('pending_report', '待確認報表'),
        ('closed', '已日結'),
        ('no_data', '沒有營業')
    ], validators=[Optional()])
    start_date = DateField('開始日期', validators=[DataRequired()], default=date.today)
    end_date = DateField('結束日期', validators=[Optional()])
    submit = SubmitField('查詢')

    def __init__(self, *args, **kwargs):
        super(ReportQueryForm, self).__init__(*args, **kwargs)
        self.location_id.choices = [('all', '所有據點')] + [(str(l.id), l.name) for l in Location.query.order_by(Location.id).all()]
