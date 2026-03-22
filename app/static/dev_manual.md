# 5 Way House 收銀系統 — 開發說明書

> **文件版本**：v1.0 &emsp; **最後更新**：2026-03-16  
> 本手冊面向後續接手的開發者，涵蓋架構設計、模組說明、資料庫結構、擴充指引與部署流程。

---

## 目錄

[TOC]

---

## 1. 技術棧總覽

| 層次 | 技術 | 說明 |
|------|------|------|
| Web 框架 | **Flask 3.x** | Application factory 模式 |
| ORM | **SQLAlchemy 2.x** + Flask-SQLAlchemy | 資料庫存取 |
| 資料庫遷移 | **Flask-Migrate** (Alembic) | Schema 版本管理 |
| 身份驗證 | **Flask-Login** + Google OAuth 2.0 | 本地帳密 + Google SSO |
| 表單驗證 | **Flask-WTF** + WTForms | CSRF 保護 |
| 背景任務 | **RQ** (Redis Queue) + Redis | 非同步備份 |
| PDF 產生 | **WeasyPrint** | HTML → PDF 轉換 |
| OCR | **pytesseract** + Pillow | 收據圖片識別 |
| Google API | **google-api-python-client** | Drive / Sheets 整合 |
| 資料庫 | **SQLite**（開發） / **PostgreSQL**（生產） | |
| 容器化 | **Docker** + **Docker Compose** | |
| 前端 | **Bootstrap 5.3** + Vanilla JS | 無前端框架 |
| Markdown 渲染 | **markdown** (Python) | 手冊頁面 |

---

## 2. 專案目錄結構

```
5_way_house/
├── app/                        # Flask 應用程式主目錄
│   ├── __init__.py             # Application factory (create_app)
│   ├── core/                   # 核心基礎設施
│   │   ├── extensions.py       # 全域 Flask 擴充實例（db, migrate, login_manager, csrf）
│   │   └── decorators.py       # 自訂裝飾器（@admin_required 等）
│   ├── modules/                # 功能模組（Domain-Driven Design）
│   │   ├── auth/               # 身份驗證模組
│   │   │   ├── models.py       # User, Role, Permission
│   │   │   └── forms.py        # LoginForm, UserForm, RoleForm
│   │   ├── store/              # 據點與商品模組
│   │   │   ├── models.py       # Location, Category
│   │   │   └── forms.py        # LocationForm, CategoryForm
│   │   ├── pos/                # 收銀交易模組
│   │   │   └── models.py       # Transaction, TransactionItem
│   │   ├── daily_ops/          # 日常營運模組
│   │   │   ├── models.py       # BusinessDay, DailySettlement
│   │   │   └── forms.py        # StartDayForm, CloseDayForm, ConfirmReportForm, SettlementForm
│   │   ├── report/             # 報表模組
│   │   │   └── forms.py        # ReportQueryForm
│   │   ├── system/             # 系統設定模組
│   │   │   ├── models.py       # SystemSetting
│   │   │   └── forms.py        # GoogleSettingsForm
│   │   ├── warehouse/          # [Phase 2] 倉庫物流管理模組
│   │   ├── workshop/           # [Phase 2] 工坊登記系統
│   │   ├── accommodation/      # [Phase 2] 住宿登錄系統
│   │   ├── volunteer/          # [Phase 2] 志工與活動管理
│   │   └── integrations/       # 第三方整合（保留供擴充）
│   ├── routes/                 # 路由 / Blueprint 層
│   │   ├── __init__.py         # Blueprint 匯入點
│   │   ├── main_routes.py      # 首頁、系統說明書
│   │   ├── cashier_routes.py   # 收銀員功能（開帳、POS、結帳）
│   │   ├── admin_routes.py     # 管理員功能
│   │   ├── report_routes.py    # 報表查詢與結算
│   │   ├── ocr_routes.py       # 收據 OCR 上傳與驗證
│   │   └── google_routes.py    # Google OAuth 授權
│   ├── services/               # 業務邏輯服務層
│   │   ├── ocr_service.py      # OCR 圖片解析
│   │   ├── google_service.py   # Google API（Drive / Sheets）
│   │   └── backup_service.py   # 雲端備份排程邏輯
│   ├── static/                 # 靜態資源
│   │   ├── css/
│   │   ├── js/
│   │   ├── images/
│   │   ├── manual.md           # 使用者手冊（Markdown 原始檔）
│   │   └── dev_manual.md       # 開發說明書（本文件，Markdown 原始檔）
│   ├── templates/              # Jinja2 模板
│   │   ├── base.html           # 主版型（Navbar、Flash 訊息）
│   │   ├── print_base.html     # 列印版型（A4 PDF）
│   │   ├── macros.html         # 共用 Macro（page_header）
│   │   ├── manual.html         # 使用者手冊網頁
│   │   ├── manual_print.html   # 使用者手冊 PDF 模板
│   │   ├── dev_manual.html     # 開發說明書網頁
│   │   ├── admin/              # 管理員頁面
│   │   ├── cashier/            # 收銀員頁面
│   │   └── report/             # 報表頁面
│   ├── auth_commands.py        # Flask CLI：帳號初始化指令
│   └── backup_commands.py      # Flask CLI：備份 CLI 指令
├── config.py                   # 多環境設定（Development / Production / Testing）
├── run.py                      # 本地啟動入口
├── wsgi.py                     # WSGI 生產入口（Gunicorn）
├── migrations/                 # Alembic 資料庫遷移歷史
├── instance/                   # 執行階段資料（不進版控）
│   ├── app.db                  # SQLite 資料庫（開發用）
│   ├── receipts/               # 存款收據圖片
│   ├── client_secret.json      # Google OAuth 憑證
│   └── token.json              # Google OAuth Token
├── Dockerfile
├── docker-compose.yml
├── .env                        # 環境變數（不進版控）
└── requirements.in / .txt      # Python 依賴管理
```

---

## 3. 架構設計理念

### Application Factory 模式

系統使用 `create_app()` 工廠函式，位於 `app/__init__.py`：

```python
def create_app(config_name='development'):
    app = Flask(__name__)
    app.config.from_object(config[config_name])
    # 初始化擴充
    db.init_app(app)
    # 註冊 Blueprint
    from app.routes import cashier_bp, admin_bp ...
    app.register_blueprint(cashier_bp)
    ...
    return app
```

好處：避免循環依賴、容易測試、支援多設定環境。

### Domain-Driven Modular Structure（DDD 模組化）

`app/modules/` 依商業領域拆分：每個子目錄是一個獨立的功能領域，包含自己的 models 和 forms。新增功能只需在 `modules/` 下建立新子目錄，不動到既有程式碼（高內聚、低耦合）。

### 三層架構

```
Routes（路由層）  →  Services（服務層）  →  Models（資料層）
     ↑                                           ↑
Templates（視圖）                         Extensions（DB, Login...）
```

---

## 4. 資料庫模型說明

### 4.1 關聯圖

```
User ─── roles_users ─── Role
                          │
Location ─┬─ BusinessDay ─┼─ Transaction ─── TransactionItem ─── Category
          └─ Category      │
                          DailySettlement
SystemSetting（獨立鍵值表）
```

### 4.2 各資料表說明

#### `user`—使用者
| 欄位 | 類型 | 說明 |
|------|------|------|
| id | Integer PK | |
| username | String(64) | 唯一 |
| password_hash | String(256) | scrypt 加密 |
| google_id | String(255) | Google SSO ID |
| email | String(120) | Google 電子郵件 |

#### `role`—角色
| 欄位 | 類型 | 說明 |
|------|------|------|
| id | Integer PK | |
| name | String(64) | Admin / Cashier |
| description | String(255) | |

#### `location`—據點
| 欄位 | 類型 | 說明 |
|------|------|------|
| id | Integer PK | |
| name | String(50) | 唯一 |
| slug | String(50) | URL 代碼，唯一 |

#### `category`—商品類別
| 欄位 | 類型 | 說明 |
|------|------|------|
| id | Integer PK | |
| name | String(50) | |
| price | Float | 單價 |
| category_type | String | `general` / `other_income` |
| location_id | FK → location | |

#### `business_day`—營業日
| 欄位 | 類型 | 說明 |
|------|------|------|
| id | Integer PK | |
| date | Date | 營業日期 |
| location_id | FK → location | |
| status | String(20) | NOT_STARTED / OPEN / PENDING_REPORT / CLOSED |
| opening_cash | Float | 開店準備金 |
| total_sales | Float | 銷售合計 |
| closing_cash | Float | 盤點現金 |
| expected_cash | Float | 帳面總額 |
| cash_diff | Float | 帳差 |
| total_items | Integer | 商品件數 |
| total_transactions | Integer | 交易筆數 |
| cash_breakdown | Text (JSON) | 現金面額明細 |
| signature_* | Text | Base64 電子簽名（3欄）|
| next_day_opening_cash | Float | 明日準備金 |
| updated_at | DateTime | |

#### `transaction`—交易
| 欄位 | 類型 | 說明 |
|------|------|------|
| id | Integer PK | |
| timestamp | DateTime | |
| amount | Float | 交易金額（含折扣後）|
| item_count | Integer | 本交易商品件數 |
| discounts | Text (JSON) | 折扣金額陣列 |
| business_day_id | FK → business_day | |

#### `transaction_item`—交易明細
| 欄位 | 類型 | 說明 |
|------|------|------|
| id | Integer PK | |
| price | Float | 單價 |
| transaction_id | FK → transaction | |
| category_id | FK → category | |

#### `daily_settlement`—合併日結
| 欄位 | 類型 | 說明 |
|------|------|------|
| id | Integer PK | |
| date | Date | 唯一，結算日期 |
| total_deposit | Float | 存款合計 (H) |
| total_next_day_opening_cash | Float | 明日開店現金 (I) |
| remarks | Text (JSON) | 各欄備註 |
| deposit_receipt_path | String(512) | 收據圖片路徑 |
| deposit_ocr_amount | Float | OCR 識別金額 |
| deposit_verified | Boolean | None=未驗證 / True=一致 / False=差異 |

#### `system_setting`—系統設定（鍵值表）
| 欄位 | 類型 | 說明 |
|------|------|------|
| key | String(50) PK | 設定鍵名 |
| value | String(200) | 設定值 |

---

## 5. 模組功能說明

### `app/modules/auth/`
- **models.py**：`User`（登入、Google SSO、密碼驗證）、`Role`（多對多關聯）、`Permission`
- **forms.py**：`LoginForm`、`UserForm`（新增/編輯使用者）、`RoleForm`

### `app/modules/store/`
- **models.py**：`Location`（據點，關聯 `BusinessDay` 與 `Category`）、`Category`（商品類別，歸屬於據點）
- **forms.py**：`LocationForm`、`CategoryForm`

### `app/modules/pos/`
- **models.py**：`Transaction`（每筆結帳交易）、`TransactionItem`（交易內的商品明細）

### `app/modules/daily_ops/`
- **models.py**：`BusinessDay`（每日每據點的營業記錄）、`DailySettlement`（跨據點合併日結）
- **forms.py**：`StartDayForm`、`CloseDayForm`（含現金盤點子表單）、`ConfirmReportForm`、`SettlementForm`（含多欄備註子表單）

### `app/modules/report/`
- **forms.py**：`ReportQueryForm`（報表查詢條件）

### `app/modules/system/`
- **models.py**：`SystemSetting`（key-value 設定，如 Google Drive 資料夾名稱）
- **forms.py**：`GoogleSettingsForm`

---

## 6. 路由與 Blueprint 說明

| Blueprint | URL Prefix | 功能 |
|-----------|-----------|------|
| `main` | `/` | 首頁、說明書 |
| `cashier` | `/cashier` | 開帳、POS、結帳、Dashboard |
| `admin` | `/admin` | 管理後台（@admin_required）|
| `report` | `/report` | 報表查詢、合併結算 |
| `ocr` | `/ocr` | 收據上傳與 OCR 驗證 |
| `google` | `/google` | Google OAuth 授權流程 |

### 主要路由清單

```
GET  /                              → 首頁
GET  /manual                        → 使用者手冊
GET  /manual/pdf                    → 使用者手冊 PDF
GET  /dev                           → 開發說明書
GET  /dev/pdf                       → 開發說明書 PDF

GET  /cashier/dashboard             → 收銀員儀表板
GET  /cashier/pos/<location_slug>   → POS 收銀介面
POST /cashier/record_transaction    → 記錄交易
GET,POST /cashier/start_day/<slug>  → 開帳
GET,POST /cashier/close_day/<slug>  → 結帳（現金盤點）
GET,POST /cashier/confirm_report/<slug> → 確認並歸檔報表

GET  /admin/locations               → 據點管理
GET  /admin/users                   → 使用者管理
GET  /admin/roles                   → 角色管理
GET  /admin/force_close_query       → 補登日結查詢
GET,POST /admin/force_close_day/new → 補登日結

GET  /report/query                  → 報表查詢
GET  /report/settlement             → 合併報表結算
POST /report/save_settlement        → 儲存合併結算
GET  /report/settlement/print/<date>→ 合併報表 PDF

POST /ocr/upload_deposit_receipt    → 上傳收據 + OCR 解析（JSON API）
POST /ocr/confirm_deposit_receipt   → 確認 OCR 結果存檔（JSON API）

GET  /google/login, /google/callback, /google/authorize_drive → Google OAuth
```

---

## 7. 核心擴充模組（Extensions）

**`app/core/extensions.py`** 統一宣告所有 Flask 擴充實例，避免循環引用：

```python
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_wtf import CSRFProtect

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
csrf = CSRFProtect()
```

> ⚠️ **重要**：所有模組必須從 `app.core.extensions` 匯入 `db`，絕對不能從其他地方重新宣告。

**`app/core/decorators.py`** 提供自訂裝飾器：

```python
@admin_required  # 要求登入且 has_role('Admin')
```

---

## 8. 表單系統（Forms）

系統使用 Flask-WTF + WTForms：

```python
from flask_wtf import FlaskForm
from wtforms import StringField, validators

class LocationForm(FlaskForm):
    name = StringField('名稱', [validators.DataRequired()])
    slug = StringField('Slug', [validators.DataRequired()])
```

- 所有表單均有 CSRF 保護（透過全域 `csrf = CSRFProtect()`）
- 在 Jinja2 模板中呼叫 `{{ form.hidden_tag() }}` 或 `{{ csrf_token() }}` 插入 CSRF token
- AJAX 請求中，ocr_routes.py 的 API 使用 `@csrf.exempt` 排除（因 multipart upload）

---

## 9. 背景任務（RQ Worker）

系統使用 **Redis + RQ** 執行非同步任務（主要是雲端備份）：

```
Flask App  →  RQ Queue  →  Redis  →  RQ Worker  →  Google API
```

**任務觸發時機**：每次管理員確認歸檔每日報表（`/cashier/confirm_report/...`）

**Worker 啟動**：

```bash
# 本地開發
source .venv/bin/activate
rq worker cashier-tasks

# Docker 環境（自動）
docker-compose up
```

**任務定義位置**：`app/services/backup_service.py`

---

## 10. Google 整合說明

### 授權流程

```
使用者 → /google/authorize_drive → Google OAuth → /google/drive_callback → 儲存 token.json
```

憑證儲存於 `instance/client_secret.json` 與 `instance/token.json`。

### 使用的 API

| API | 功能 |
|-----|------|
| Google Drive API v3 | 備份 PDF 報表上傳 |
| Google Sheets API v4 | 寫入銷售數據 |
| Google OAuth 2.0 | 使用者身份驗證（Google SSO） |

### 服務入口

`app/services/google_service.py` — 封裝 Drive / Sheets 操作：

```python
from app.services.google_service import get_services
drive_service, sheets_service = get_services()
```

---

## 11. OCR 服務說明

**位置**：`app/services/ocr_service.py`

### 核心函式

```python
# 從圖片提取存款金額
result = extract_deposit_amount(image_path)
# → {"success": bool, "amount": float|None, "raw_text": str, "error": str|None}

# 比對系統金額與 OCR 金額
cmp = compare_amounts(system_amount, ocr_amount, tolerance=1.0)
# → {"match": bool, "difference": float}
```

### 識別邏輯

1. 圖片前處理（灰階、增強對比、銳化）
2. Tesseract OCR（lang=`chi_tra+eng`，psm=6）
3. 正規表達式提取金額（優先匹配中文標籤 + 數字，最後回退到最大純數字）

### 注意事項

- 系統需預先安裝 `tesseract-ocr` 與中文語言包（見 Dockerfile）
- `chi_tra` 語言包需安裝 `tesseract-ocr-chi-tra`

---

## 12. 前端架構說明

### 模板繼承結構

```
base.html               ← 一般頁面的母模板（含 Navbar、Flash、Bootstrap CSS/JS）
└── 所有一般頁面.html

print_base.html         ← 列印/PDF 頁面的母模板（A4 樣式、無 Navbar）
└── report_print.html
└── settlement_print.html
└── manual_print.html
```

### 共用 Macro

**`templates/macros.html`** 中的 `page_header` macro，統一所有頁面標題：

```html
{% from "macros.html" import page_header with context %}
{{ page_header(title='頁面標題', subtitle='副標題', button_url=..., button_text='按鈕') }}
```

### JavaScript 原則

- 使用原生 Vanilla JS（無框架依賴）
- AJAX 使用 `fetch()` API
- 格式化金額使用 `Intl.NumberFormat`

---

## 13. 安全機制

| 機制 | 說明 |
|------|------|
| CSRF 保護 | 全域 `CSRFProtect`，所有表單自動保護 |
| 密碼加密 | Werkzeug `generate_password_hash`（scrypt）|
| 身份驗證 | Flask-Login，所有受保護路由加 `@login_required` |
| 管理員驗證 | 自訂 `@admin_required` 裝飾器（二重保護）|
| Session 安全 | `SESSION_COOKIE_SECURE`、`SESSION_COOKIE_HTTPONLY`、`SESSION_COOKIE_SAMESITE='Lax'` |
| 資料庫注入 | SQLAlchemy ORM Parameterized Query（原生防禦）|
| 敏感設定 | 所有金鑰/憑證從環境變數讀取（`.env`）|
| Gold Key 輪換 | 每次部署建議更換 `SECRET_KEY` |

---

## 14. 新增功能開發指引

### 14.1 新增一個功能模組（例如：會員積點）

**步驟一**：建立模組目錄

```
app/modules/loyalty/
├── __init__.py
├── models.py    ← 定義 LoyaltyCard, PointTransaction 等 Model
└── forms.py     ← 定義相關 Form
```

**步驟二**：定義模型（`models.py`）

```python
from app.core.extensions import db

class LoyaltyCard(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    card_number = db.Column(db.String(20), unique=True, nullable=False)
    points = db.Column(db.Integer, default=0)
```

**步驟三**：建立路由（`app/routes/loyalty_routes.py`）

```python
from flask import Blueprint, render_template
from flask_login import login_required

bp = Blueprint('loyalty', __name__, url_prefix='/loyalty')

@bp.route('/')
@login_required
def index():
    return render_template('loyalty/index.html')
```

**步驟四**：在 `app/routes/__init__.py` 中匯入並在 `app/__init__.py` 中註冊 Blueprint

**步驟五**：建立模板 `app/templates/loyalty/index.html`

```html
{% extends "base.html" %}
{% from "macros.html" import page_header with context %}
{% block title %}會員積點{% endblock %}
{% block content %}
{{ page_header(title='會員積點') }}
{% endblock %}
```

**步驟六**：執行資料庫遷移

```bash
flask db migrate -m "Add loyalty module"
flask db upgrade
```

### 14.2 新增 API 端點（JSON 回傳）

```python
from flask import jsonify, request

@bp.route('/api/points/<int:card_id>', methods=['GET'])
@login_required
def get_points(card_id):
    card = LoyaltyCard.query.get_or_404(card_id)
    return jsonify({"card_number": card.card_number, "points": card.points})
```

### 14.3 新增背景任務

```python
# 在 services/loyalty_service.py 定義任務函式
def send_points_email(card_id, points):
    # 執行耗時操作...
    pass

# 在路由中加入任務隊列
from rq import Queue
from redis import Redis
q = Queue('cashier-tasks', connection=Redis())
q.enqueue(send_points_email, card_id, points)
```

---

## 15. Docker 與部署說明

### 服務架構

```yaml
# docker-compose.yml
services:
  web:     # Flask 主服務（Gunicorn）Port 5000
  worker:  # RQ Worker（背景任務）
  redis:   # Redis 訊息佇列
```

### 15.1 全新部署流程（包含 Docker 安裝與初始設定）

當您接手系統需要安裝至伺服器或本機開發環境時：

**步驟一、環境準備**
- 請確認伺服器已安裝 **Docker** 及 **Docker Compose**。
- 若尚未安裝，請依據作業系統至 [Docker 官網](https://docs.docker.com/engine/install/) 執行一鍵指令（Linux 常見指令為 `curl -fsSL https://get.docker.com -o get-docker.sh && sh get-docker.sh`）。

**步驟二、取得程式授權與環境設定**
```bash
# 下載與進入專案目錄
git clone <專案的_Git_URL> 5_way_house
cd 5_way_house

# 複製並設定本地環境變數檔
cp .env.example .env
# 請務必編輯 .env 檔案，填寫強密碼 SECRET_KEY 避免資安外流
```

**步驟三、透過 Docker Compose 編譯與啟動服務**
```bash
# 這將花費 2~5 分鐘下載並編譯 Python 與必要的 OCR/PDF 工具
# 系統啟動時會自動建立資料庫、預設角色(Admin等)與管理員帳號(admin/password)
docker-compose --env-file .env up -d --build
```

**步驟四、登入大都會收銀系統**
啟動完成後，即可前往 `http://<您的伺服器IP>:5001` 登入系統！
預設帳號密碼為：
- 帳號：`admin`
- 密碼：`password`


### 15.2 常用維運指令

```bash
# 啟動所有服務 (背景執行)
docker-compose --env-file .env up -d

# 進入 web 容器終端機
docker-compose exec web bash

# 查看網站防護與連線日誌 (追蹤 Bug 必用)
docker-compose logs -f web
docker-compose logs -f worker

# 停止並關閉服務
docker-compose down
```

### Dockerfile 重點

- 基礎映像：`python:3.12-slim`
- 已預先安裝：WeasyPrint 依賴（libpango、fonts-noto-cjk）、tesseract-ocr

---

## 16. 資料庫遷移作業

```bash
# 1. 建立新的遷移版本（在修改 models.py 後執行）
flask db migrate -m "描述變更內容"

# 2. 套用遷移到資料庫
flask db upgrade

# 3. 回滾到上一版本
flask db downgrade

# 4. 查看遷移歷史
flask db history
```

> ⚠️ **生產環境注意**：遷移前務必備份資料庫！

---

## 17. 常用 CLI 指令

```bash
# 初始化角色（首次部署）
flask auth init-roles

# 建立管理員帳號
flask auth create-user <username> <password> --role Admin

# 觸發即時備份
flask backup run-now

# 檢視所有路由
flask routes

# 語法編譯檢查
python3 -m compileall app/
```

---

## 18. Phase 2 開發指引與架構預留 (Scaffolding Guideline)
目前四大未來的子系統已經在系統 codebase 中完成目錄預留，與 Portal 首頁的預留連結。後續開發者接手時，請依照下列模型規範疊加程式碼：

### 📁 目錄結構擴充
所有 Phase 2 的 Domain 模組皆已對應置放於 `app/modules/` 底下：

- **`app/modules/warehouse/`** 倉庫管理
  - **系統目標**：貨物分類後進入倉庫的登記、出貨到店鋪的登記。
  - **檔案建立指南**：
    - `models.py`: 建立 `WarehouseItem` (庫存表), `StockTransaction` (進出庫明細)
    - `forms.py`: 建立 `ItemInForm` (入庫表單), `ItemOutForm` (出庫表單)
    - `routes.py`: 建議建立 `warehouse_bp` (Blueprint) 並綁定 URL `/warehouse`

- **`app/modules/workshop/`** 工坊登記系統
  - **系統目標**：貨到登記箱數、開箱使用 OCR 掃描並登記寄件人資訊。
  - **檔案建立指南**：
    - `models.py`: 建立 `DonationBox` (包裹分類物件), `DonorInfo` (寄件人資料表)
    - `forms.py`: 建立 `PackageReceiptForm` (收件表單), `OCRVerifyForm` (OCR 辨識資料修正與校驗)

- **`app/modules/accommodation/`** 住宿登錄系統
  - **系統目標**：設定多個住宿地點、每個住宿地點的房間數量、類型、可容納人數、登記住宿時段。
  - **檔案建立指南**：
    - `models.py`: 建立 `AccommodationLocation` (住宿地點表), `Room` (房間類別與容納限制), `Booking` (住宿時段檔期登記表)
    - `forms.py`: `LocationSetupForm`, `RoomSetupForm`, `BookingForm`

- **`app/modules/volunteer/`** 志工與活動管理系統
  - **系統目標**：開設活動、登錄志工信息、生成該活動志工的感謝狀 / 證明狀 (系統需可設定多個活動與不同的證書模板)。
  - **檔案建立指南**：
    - `models.py`: 建立 `VolunteerActivity` (活動主檔表), `Volunteer` (志工檔), `CertificateTemplate` (感謝狀前端樣板與參數欄位)
    - `forms.py`: `ActivityForm`, `VolunteerEnrollForm`, `CertificateConfigForm`

### 🔧 路由與 RBAC 權限層面調用
1. **註冊藍圖**：將上述模組內的 `routes.py` 所生成的 `X_bp`，統一放入 `app/routes/__init__.py` 或 `create_app()` 中執行路由註冊。
2. **存取權限控管**：系統底層 RBAC 已經在 `app/modules/auth/models.py` 的 `Permission` 類別中預留好了四大常數：`ACCESS_WAREHOUSE`, `ACCESS_WORKSHOP`, `ACCESS_ACCOMMODATION`, `ACCESS_VOLUNTEER`。
3. 未來新增之 Controller (MethodView) 類別請務必在 `get()` 或 `post()` 附帶對應的權限檢查邏輯：
    ```python
    if not current_user.can(Permission.ACCESS_WORKSHOP):
        abort(403)
    ```
    確保不同職務的模組人員彼此獨立不受干擾。
