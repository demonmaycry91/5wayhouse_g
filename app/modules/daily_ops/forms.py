from flask_wtf import FlaskForm
from wtforms import FloatField, TextAreaField, SubmitField, HiddenField, StringField, FormField, FieldList
from wtforms.validators import DataRequired, Length, Optional

class StartDayForm(FlaskForm):
    opening_cash = FloatField('開店準備金 (元)', validators=[
        DataRequired(message="請輸入開店準備金。")
    ])
    location_notes = TextAreaField('備註 (選填)', validators=[Length(max=200)])
    submit = SubmitField('確認開始營業')

class CloseDayForm(FlaskForm):
    submit = SubmitField('送出盤點結果並預覽報表')

class ConfirmReportForm(FlaskForm):
    submit = SubmitField('確認存檔並結束本日營業')

class SettlementRemarkForm(FlaskForm):
    key = HiddenField()
    value = StringField()

class SettlementForm(FlaskForm):
    date = HiddenField()
    total_deposit = FloatField(validators=[Optional()])
    total_next_day_opening_cash = FloatField(validators=[DataRequired(message="請輸入明日開店現金。")])
    remarks = FieldList(FormField(SettlementRemarkForm), min_entries=11)
    submit = SubmitField('儲存所有明日開店現金')
