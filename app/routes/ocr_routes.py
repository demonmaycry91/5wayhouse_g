"""
app/routes/ocr_routes.py
收據 OCR 上傳路由
"""
import os
import uuid
from flask import Blueprint, request, jsonify, current_app, send_from_directory
from flask.views import MethodView
from flask_login import login_required, current_user

from PIL import Image
from datetime import date as date_type

from app.core.extensions import csrf, db
from app.services.ocr_service import OCRService
from app.modules.daily_ops.models import DailySettlement

bp = Blueprint('ocr', __name__, url_prefix='/ocr')

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
ALLOWED_PILLOW_FORMATS = {'PNG', 'JPEG', 'GIF', 'WEBP'}

# ==========================================
# Helpers
# ==========================================
def _allowed_file(filename: str) -> bool:
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def _validate_image_mime(file_obj) -> bool:
    try:
        img = Image.open(file_obj)
        fmt = img.format
        file_obj.seek(0)
        return fmt in ALLOWED_PILLOW_FORMATS
    except Exception:
        file_obj.seek(0)
        return False

# ==========================================
# Base Views
# ==========================================
class OCRBaseView(MethodView):
    """Base class for all OCR operations requiring login"""
    decorators = [login_required]

# ==========================================
# Views
# ==========================================
class OCRPageView(OCRBaseView):
    def get(self):
        return "OCR service is active."

class ServeReceiptView(OCRBaseView):
    def get(self, filename):
        """安全的收據圖片服務路由 — 限登入後才可訪問"""
        receipts_dir = os.path.join(current_app.instance_path, 'receipts')
        safe_filename = os.path.basename(filename)
        return send_from_directory(receipts_dir, safe_filename)

class UploadDepositReceiptView(OCRBaseView):
    decorators = [login_required, csrf.exempt]
    
    def post(self):
        if 'file' not in request.files:
            return jsonify({"success": False, "error": "未收到圖片檔案"}), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({"success": False, "error": "尚未選擇圖片"}), 400

        if not _allowed_file(file.filename):
            return jsonify({"success": False, "error": "不支援的圖片格式，請上傳 JPG / PNG / WEBP"}), 400

        if not _validate_image_mime(file):
            return jsonify({"success": False, "error": "檔案格式不符，僅接受真實圖片檔案"}), 400

        settlement_date_str = request.form.get('settlement_date')
        system_amount_str = request.form.get('system_amount')

        try: system_amount = float(system_amount_str) if system_amount_str else None
        except ValueError: system_amount = None

        receipts_dir = os.path.join(current_app.instance_path, 'receipts')
        os.makedirs(receipts_dir, exist_ok=True)

        ext = file.filename.rsplit('.', 1)[1].lower()
        unique_filename = f"{settlement_date_str}_{uuid.uuid4().hex[:8]}.{ext}"
        save_path = os.path.join(receipts_dir, unique_filename)
        file.save(save_path)

        ocr_result = OCRService.extract_deposit_amount(save_path)
        if not ocr_result["success"]:
            return jsonify({"success": False, "error": f"OCR 解析失敗：{ocr_result['error']}", "ocr_amount": None, "match": None, "difference": None, "receipt_path": unique_filename})

        ocr_amount = ocr_result["amount"]
        comparison = OCRService.compare_amounts(system_amount, ocr_amount, tolerance=1.0) if system_amount is not None and ocr_amount is not None else {"match": None, "difference": None}

        return jsonify({"success": True, "ocr_amount": ocr_amount, "raw_text": ocr_result["raw_text"], "match": comparison["match"], "difference": comparison["difference"], "receipt_path": unique_filename, "error": None})

class ConfirmDepositReceiptView(OCRBaseView):
    decorators = [login_required, csrf.exempt]
    
    def post(self):
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "缺少請求資料"}), 400

        settlement_date_str = data.get('settlement_date')
        receipt_path = data.get('receipt_path')
        ocr_amount = data.get('ocr_amount')
        verified = data.get('verified')

        try: settlement_date = date_type.fromisoformat(settlement_date_str)
        except (ValueError, TypeError): return jsonify({"success": False, "error": "無效的日期格式"}), 400

        settlement = DailySettlement.query.filter_by(date=settlement_date).first()
        if not settlement:
            return jsonify({"success": False, "error": "找不到對應的結算記錄"}), 404

        settlement.deposit_receipt_path = receipt_path
        settlement.deposit_ocr_amount = ocr_amount
        settlement.deposit_verified = verified
        settlement.deposit_uploader_id = current_user.id

        try:
            db.session.commit()
            return jsonify({"success": True})
        except Exception as e:
            db.session.rollback()
            return jsonify({"success": False, "error": str(e)}), 500

# ==========================================
# Route Registrations
# ==========================================
bp.add_url_rule('/', view_func=OCRPageView.as_view('ocr_page'))
bp.add_url_rule('/receipts/<path:filename>', view_func=ServeReceiptView.as_view('serve_receipt'))
bp.add_url_rule('/upload_deposit_receipt', view_func=UploadDepositReceiptView.as_view('upload_deposit_receipt'))
bp.add_url_rule('/confirm_deposit_receipt', view_func=ConfirmDepositReceiptView.as_view('confirm_deposit_receipt'))
