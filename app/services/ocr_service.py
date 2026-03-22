import re
import os
import pytesseract
from PIL import Image, ImageFilter, ImageEnhance

class OCRService:
    """銀行存款收據 OCR 解析服務"""
    
    _AMOUNT_PATTERNS = [
        r'(?:存款|存入|金額|合計|總計|匯款)[：:\s]*\$?\s*([0-9][0-9,\.]+)',
        r'(?:AMOUNT|DEPOSIT|TOTAL)[：:\s]*\$?\s*([0-9][0-9,\.]+)',
        r'(?:NT\$|NTD|TWD)\s*([0-9][0-9,\.]+)',
        r'([0-9]{3,}(?:,[0-9]{3})*(?:\.[0-9]{1,2})?)',
    ]

    @staticmethod
    def _preprocess_image(image: Image.Image) -> Image.Image:
        image = image.convert('L')
        enhancer = ImageEnhance.Contrast(image)
        image = enhancer.enhance(2.0)
        image = image.filter(ImageFilter.SHARPEN)
        return image

    @classmethod
    def _parse_amount_from_text(cls, text: str) -> float | None:
        for pattern in cls._AMOUNT_PATTERNS[:-1]:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                try: return float(matches[0].replace(',', ''))
                except ValueError: continue

        fallback_matches = re.findall(cls._AMOUNT_PATTERNS[-1], text)
        if fallback_matches:
            amounts = []
            for m in fallback_matches:
                try: amounts.append(float(m.replace(',', '')))
                except ValueError: pass
            if amounts:
                return max(amounts)
        return None

    @classmethod
    def extract_deposit_amount(cls, image_path: str) -> dict:
        if not os.path.exists(image_path):
            return {"success": False, "amount": None, "raw_text": "", "error": "圖片檔案不存在"}

        try:
            image = Image.open(image_path)
            image = cls._preprocess_image(image)
            try:
                raw_text = pytesseract.image_to_string(image, lang='chi_tra+eng', config='--psm 6')
            except pytesseract.pytesseract.TesseractError:
                raw_text = pytesseract.image_to_string(image, lang='eng', config='--psm 6')

            amount = cls._parse_amount_from_text(raw_text)
            return {"success": True, "amount": amount, "raw_text": raw_text.strip(), "error": None}
        except Exception as e:
            return {"success": False, "amount": None, "raw_text": "", "error": str(e)}

    @staticmethod
    def compare_amounts(system_amount: float, ocr_amount: float, tolerance: float = 1.0) -> dict:
        if ocr_amount is None:
            return {"match": False, "difference": None}
        difference = abs(system_amount - ocr_amount)
        return {"match": difference <= tolerance, "difference": round(system_amount - ocr_amount, 2)}
