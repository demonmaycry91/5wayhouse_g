from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, SelectMultipleField, widgets
from wtforms.validators import DataRequired, Length, Regexp, EqualTo, ValidationError
from .models import User, Role

class LoginForm(FlaskForm):
    username = StringField('帳號', validators=[DataRequired(message="請輸入帳號。")])
    password = PasswordField('密碼', validators=[DataRequired(message="請輸入密碼。")])
    submit = SubmitField('登入')

class RoleForm(FlaskForm):
    name = StringField('角色名稱', validators=[DataRequired(), Length(1, 64)])
    permissions = SelectMultipleField(
        '權限', 
        coerce=str, 
        widget=widgets.ListWidget(prefix_label=False), 
        option_widget=widgets.CheckboxInput()
    )
    submit = SubmitField('儲存')

class UserForm(FlaskForm):
    username = StringField('使用者名稱', validators=[DataRequired(), Length(1, 64), Regexp('^[A-Za-z][A-Za-z0-9_.]*$', 0, '使用者名稱只能包含字母、數字、點或底線')])
    password = PasswordField('密碼', validators=[
        EqualTo('password2', message='兩次輸入的密碼必須相符。')
    ])
    password2 = PasswordField('確認密碼')
    roles = SelectMultipleField(
        '角色', 
        coerce=int,
        widget=widgets.ListWidget(prefix_label=False), 
        option_widget=widgets.CheckboxInput()
    )
    submit = SubmitField('儲存')

    def __init__(self, user=None, *args, **kwargs):
        super(UserForm, self).__init__(*args, **kwargs)
        self.original_user = user
        self.roles.choices = [(r.id, r.name) for r in Role.query.order_by('name').all()]

    def validate_username(self, field):
        if self.original_user is None or self.original_user.username != field.data:
            if User.query.filter_by(username=field.data).first():
                 raise ValidationError('此使用者名稱已被使用。')
