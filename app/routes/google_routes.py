import os
import requests
from flask import Blueprint, redirect, url_for, session, request, current_app, flash
from flask.views import MethodView
from flask_login import login_user

from google_auth_oauthlib.flow import Flow
from app.services.google_service import GoogleIntegrationService
from app.modules.auth.models import User, Role
from app.core.extensions import db

bp = Blueprint('google', __name__, url_prefix='/google')

DRIVE_SCOPES = ['https://www.googleapis.com/auth/drive', 'https://www.googleapis.com/auth/spreadsheets']
LOGIN_SCOPES = ['openid', 'https://www.googleapis.com/auth/userinfo.email', 'https://www.googleapis.com/auth/userinfo.profile']

# ==========================================
# Base Views
# ==========================================
class GoogleAuthBaseView(MethodView):
    """Base class for handling Google Auth logic"""
    pass

# ==========================================
# User Login Flow
# ==========================================
class LoginView(GoogleAuthBaseView):
    def get(self):
        GoogleIntegrationService.write_creds_from_env(current_app)
        client_secrets_file = os.path.join(current_app.instance_path, 'client_secret.json')
        org_domain = os.getenv('ORGANIZATION_DOMAIN')

        flow = Flow.from_client_secrets_file(
            client_secrets_file, scopes=LOGIN_SCOPES, redirect_uri=url_for('google.callback', _external=True)
        )
        
        auth_url_params = {'access_type': 'offline', 'include_granted_scopes': 'true'}
        if org_domain: auth_url_params['hd'] = org_domain

        authorization_url, state = flow.authorization_url(**auth_url_params)
        session['state'] = state
        return redirect(authorization_url)

class CallbackView(GoogleAuthBaseView):
    def get(self):
        client_secrets_file = os.path.join(current_app.instance_path, 'client_secret.json')
        org_domain = os.getenv('ORGANIZATION_DOMAIN')

        flow = Flow.from_client_secrets_file(
            client_secrets_file, scopes=LOGIN_SCOPES, state=session.get('state'), redirect_uri=url_for('google.callback', _external=True)
        )
        
        try:
            flow.fetch_token(authorization_response=request.url)
        except Exception as e:
            flash(f'無法從 Google 獲取 Token: {e}', 'danger')
            return redirect(url_for('auth.login'))

        credentials = flow.credentials
        userinfo_response = requests.get('https://www.googleapis.com/oauth2/v1/userinfo', headers={'Authorization': f'Bearer {credentials.token}'})
        
        if not userinfo_response.ok:
            flash('無法從 Google 獲取使用者資訊。', 'danger')
            return redirect(url_for('auth.login'))
            
        user_info = userinfo_response.json()
        google_id = user_info['id']
        email = user_info['email']
        
        if org_domain and not email.endswith(f'@{org_domain}'):
            flash(f'登入失敗。只允許使用 @{org_domain} 網域的帳號。', 'danger')
            return redirect(url_for('cashier.login'))

        user = User.query.filter_by(google_id=google_id).first()
        if user is None:
            user = User(username=email.split('@')[0], email=email, google_id=google_id)
            cashier_role = Role.query.filter_by(name='Cashier').first()
            if cashier_role: user.roles.append(cashier_role)
            db.session.add(user)
            db.session.commit()
            flash('已成功透過 Google 帳號註冊！管理員將會為您指派權限。', 'info')

        login_user(user)
        flash('已成功透過 Google 登入！', 'success')
        return redirect(url_for('cashier.dashboard'))

# ==========================================
# Drive Authorization Flow
# ==========================================
class AuthorizeDriveView(GoogleAuthBaseView):
    def get(self):
        GoogleIntegrationService.write_creds_from_env(current_app)
        client_secrets_file = os.path.join(current_app.instance_path, 'client_secret.json')
        org_domain = os.getenv('ORGANIZATION_DOMAIN')

        flow = Flow.from_client_secrets_file(
            client_secrets_file, scopes=DRIVE_SCOPES, redirect_uri=url_for('google.drive_callback', _external=True)
        )
        
        auth_url_params = {'access_type': 'offline', 'include_granted_scopes': 'true', 'prompt': 'consent'}
        if org_domain: auth_url_params['hd'] = org_domain
            
        authorization_url, state = flow.authorization_url(**auth_url_params)
        session['drive_auth_state'] = state
        return redirect(authorization_url)

class DriveCallbackView(GoogleAuthBaseView):
    def get(self):
        client_secrets_file = os.path.join(current_app.instance_path, 'client_secret.json')
        token_file = os.path.join(current_app.instance_path, 'token.json')
        org_domain = os.getenv('ORGANIZATION_DOMAIN')

        state = session.get('drive_auth_state')
        flow = Flow.from_client_secrets_file(
            client_secrets_file, scopes=DRIVE_SCOPES, state=state, redirect_uri=url_for('google.drive_callback', _external=True)
        )
        
        try:
            flow.fetch_token(authorization_response=request.url)
        except Exception as e:
            flash(f'無法從 Google 獲取 Token: {e}', 'danger')
            return redirect(url_for('cashier.settings'))

        credentials = flow.credentials
        userinfo_response = requests.get('https://www.googleapis.com/oauth2/v1/userinfo', headers={'Authorization': f'Bearer {credentials.token}'})
        
        if not userinfo_response.ok:
            flash('無法從 Google 獲取使用者資訊。', 'danger')
            return redirect(url_for('cashier.settings'))

        user_info = userinfo_response.json()
        email = user_info['email']

        if org_domain and not email.endswith(f'@{org_domain}'):
            flash(f'授權失敗。只允許使用 @{org_domain} 網域的帳號進行雲端備份。', 'danger')
            return redirect(url_for('cashier.settings'))
            
        with open(token_file, 'w') as token:
            token.write(credentials.to_json())

        flash('已成功連結至您的 Google 帳號以進行雲端備份！', 'success')
        return redirect(url_for('cashier.settings'))

# ==========================================
# Route Registrations
# ==========================================
bp.add_url_rule('/login', view_func=LoginView.as_view('login'))
bp.add_url_rule('/callback', view_func=CallbackView.as_view('callback'))
bp.add_url_rule('/authorize_drive', view_func=AuthorizeDriveView.as_view('authorize_drive'))
bp.add_url_rule('/drive_callback', view_func=DriveCallbackView.as_view('drive_callback'))