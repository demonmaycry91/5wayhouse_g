"""
app/services/pdf_service.py
PDF 生成服務

將分散的 WeasyPrint PDF 匯出邏輯封裝為領域導向服務類別。
"""
from weasyprint import HTML

class PDFGeneratorService:
    @staticmethod
    def generate_pdf(html_string: str, base_url: str) -> bytes:
        """
        將 HTML 字串搭配 base_url（供資源索引用）轉換為 PDF bytes。
        """
        return HTML(string=html_string, base_url=base_url).write_pdf()
