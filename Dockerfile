FROM python:3.12-slim

# 設定環境變數
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# 安裝 WeasyPrint 及 PostgreSQL 系統依賴庫
# Pango, cairo, fontconfig 用於 WeasyPrint 產生 PDF
RUN apt-get update && apt-get install -y \
    build-essential \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libffi-dev \
    libxml2-dev \
    libxslt1-dev \
    libjpeg-dev \
    zlib1g-dev \
    # 加入中文字型支援，避免 WeasyPrint 產出的 PDF 中文變方塊
    fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*

# 設定工作目錄
WORKDIR /app

# 複製 requirements.txt 並安裝 Python 依賴
COPY requirements.txt /app/
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# 複製專案原始碼
COPY . /app/

# 暴露 Flask 預設 Port (雖然 Gunicorn 會處理，但作為文件聲明)
EXPOSE 5000

# 啟動腳本與權限設定 (如果有需要的話)，預設可直接在 docker-compose 內定義 command
# CMD ["gunicorn", "--bind", "0.0.0.0:5000", "run:app"]
