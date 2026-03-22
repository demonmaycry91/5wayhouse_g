import os
import markdown as md_lib
from flask import Blueprint, render_template, current_app, Response
from flask.views import MethodView
from flask_login import login_required
from app.services.pdf_service import PDFGeneratorService

from app.core.decorators import admin_required

bp = Blueprint('main', __name__)

# ==========================================
# Helpers
# ==========================================
def _load_markdown_html(filename: str) -> tuple[str, str]:
    """讀取 markdown 檔案並轉換為 HTML。"""
    manual_path = os.path.join(current_app.root_path, 'static', filename)
    with open(manual_path, encoding='utf-8') as f:
        raw = f.read()
    from markdown.extensions.toc import slugify_unicode
    md = md_lib.Markdown(
        extensions=['tables', 'fenced_code', 'toc', 'nl2br', 'attr_list'],
        extension_configs={'toc': {'slugify': slugify_unicode}}
    )
    return md.convert(raw), md.toc

# ==========================================
# Base Views
# ==========================================
class AdminRequiredView(MethodView):
    """Base class requiring both login and admin rights"""
    decorators = [login_required, admin_required]

class LoginRequiredView(MethodView):
    """Base class requiring only login"""
    decorators = [login_required]

# ==========================================
# Application Views
# ==========================================
class IndexView(MethodView):
    def get(self):
        return render_template('index.html')

class ManualView(LoginRequiredView):
    def get(self):
        """在線上閱覽系統使用手冊。"""
        manual_html, manual_toc = _load_markdown_html('manual.md')
        return render_template('manual.html', manual_html=manual_html, manual_toc=manual_toc)

class ManualPDFView(LoginRequiredView):
    def get(self):
        """將系統使用手冊匯出為 PDF。"""
        manual_html, _ = _load_markdown_html('manual.md')
        full_html = render_template('manual_print.html', manual_html=manual_html)
        pdf = WeasyHTML(string=full_html, base_url=current_app.root_path).write_pdf()
        return Response(
            pdf,
            mimetype='application/pdf',
            headers={'Content-Disposition': 'attachment; filename=5WayHouse_UserManual.pdf'}
        )

class ComingSoonView(LoginRequiredView):
    def get(self):
        """開發中功能預留頁面 (Phase 2)"""
        return render_template('coming_soon.html')

class DevManualView(AdminRequiredView):
    def get(self):
        """在線上閱覽開發說明書（僅限管理員）。"""
        manual_html, manual_toc = _load_markdown_html('dev_manual.md')
        return render_template('dev_manual.html', manual_html=manual_html, manual_toc=manual_toc)

class DevManualPDFView(AdminRequiredView):
    def get(self):
        """將開發說明書匯出為 PDF（僅限管理員）。"""
        manual_html, _ = _load_markdown_html('dev_manual.md')
        full_html = render_template('dev_manual_print.html', manual_html=manual_html)
        pdf = PDFGeneratorService.generate_pdf(full_html, current_app.root_path)
        return Response(
            pdf,
            mimetype='application/pdf',
            headers={'Content-Disposition': 'attachment; filename=5WayHouse_DevManual.pdf'}
        )

# ==========================================
# Route Registrations
# ==========================================
bp.add_url_rule('/', view_func=IndexView.as_view('index'))
bp.add_url_rule('/manual', view_func=ManualView.as_view('manual'))
bp.add_url_rule('/manual/pdf', view_func=ManualPDFView.as_view('manual_pdf'))
bp.add_url_rule('/dev', view_func=DevManualView.as_view('dev_manual'))
bp.add_url_rule('/dev/pdf', view_func=DevManualPDFView.as_view('dev_manual_pdf'))
bp.add_url_rule('/coming-soon', view_func=ComingSoonView.as_view('coming_soon'))
