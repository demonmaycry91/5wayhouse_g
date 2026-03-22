from flask_wtf import FlaskForm
from wtforms import StringField, BooleanField, RadioField, IntegerField, SubmitField
from wtforms.validators import DataRequired, Optional, NumberRange

class GoogleSettingsForm(FlaskForm):
    drive_folder_name = StringField(
        'Google Drive 資料夾名稱',
        validators=[DataRequired(message="請輸入資料夾名稱。")],
        description="所有報表將會備份到您 Google Drive 中以此名稱命名名的資料夾。"
    )
    sheets_filename_format = StringField(
        'Google Sheets 檔名格式',
        validators=[DataRequired(message="請輸入檔名格式。")],
        description="支援的變數: {location_name}, {location_slug}, {year}, {month}。例如: {location_name}_{year}_業績"
    )
    backup_db = BooleanField('備份 app.db (資料庫檔案)')
    backup_token = BooleanField('備份 token.json (Google 備份憑證)')
    backup_client_secret = BooleanField('備份 client_secret.json (Google 應用程式憑證)')

    backup_frequency = RadioField(
        '自動備份頻率',
        choices=[
            ('off', '關閉'),
            ('startup', '每次啟動時'),
            ('shutdown', '每次關閉時'),
            ('interval', '固定間隔')
        ],
        default='off'
    )
    backup_interval_minutes = IntegerField('間隔分鐘數 (僅適用於固定間隔)', validators=[Optional(), NumberRange(min=1)])

    # POS UI Settings
    pos_checkout_delay_seconds = IntegerField('POS 結帳完成明細停留秒數', default=3, validators=[Optional(), NumberRange(min=1, max=60)])
    submit = SubmitField('儲存設定')
