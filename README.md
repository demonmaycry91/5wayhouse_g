# 5 Way House 營運與結帳整合系統 (大都會)

本系統是一個專為五味屋及其相關據點開發的現代化 Web 應用程式。我們將實體店鋪收銀 POS、倉庫物流、工作坊登記、志工排班與住宿管理整合成單一入口。

系統具備**極度精細的權限隔離 (Fine-Grained RBAC)** 以及**據點地理屏障 (Location-Binding)**，並內建了與 Google Drive/Sheets API 的自動日結報表雲端備份對接機制。

---

## 🚀 系統安裝與啟動 (一鍵 Docker 部署)

為了簡化繁雜的 Python 版本環境與系統依賴庫（如 Redis, WeasyPrint PDF 引擎, OCR 引擎），我們已經全面升級為 **Docker 真・零門檻部署架構**。不論您使用 Windows, macOS 或 Linux，只要安裝了 Docker 即可瞬間啟動。

### 步驟 1：取得專案與環境變數
請開啟終端機 (Terminal)，執行以下指令：

```bash
# 1. 下載專案原始碼
git clone https://github.com/demonmaycry91/5wayhouse_g.git 5_way_house
cd 5_way_house

# 2. 複製預設環境變數檔
cp .env.example .env

# （選擇性）若是在正式公開的伺服器上，請務必開啟 .env 並修改 SECRET_KEY 為複雜亂碼。
```

### 步驟 2：一鍵編譯與啟動服務
系統內附有 `entrypoint.sh` 自動化排程，它會自動幫您完成資料庫的建立、權限的寫入以及預設帳號的生成。

```bash
# 啟動容器群組 (背景執行)
# 第一次執行時需要 2~5 分鐘的時間自動下載並編譯所需套件。
docker-compose --env-file .env up -d --build
```

當指令執行完畢，代表系統的 Flask 伺服器、Redis 資料庫與 RQ 背景工作排程器均已上線！

### 步驟 3：登入大都會主控台
現在，請打開您的瀏覽器前往：
👉 **http://localhost:5001** 或 `http://<您的伺服器IP>:5001`

（若要關閉系統，請在終端機輸入 `docker-compose down` 即可安全停機。）

---

## 🔑 預設測試帳號配置

只要是透過上述 `docker-compose` 指令第一次全新啟動，系統將自動配置好 **6 個對應不同模組權限的測試帳號**。以下帳號之預設密碼均為：**`123456`**

| 帳號 (Username) | 綁定角色 (Role) | 權限能見範圍 |
|------------------|----------------|----------------|
| `admin`          | Admin          | **全域最高管理權限**，可新增據點、修改人員職務與跨區看報表。|
| `cashier`        | Cashier        | 只允許進入收銀台 (POS) 操作與日結，無權查看總體報表。|
| `logistician`    | Logistic       | 進入倉庫物流管理模組。|
| `artisan`        | Workshop       | 進入工坊登記登錄模組。|
| `reception`      | Reception      | 進入住宿時段安排模組。|
| `coordinator`    | Coordinator    | 進入志工與活動管理模組。|

⚠️ **資安警告**：請於「正式上線」部署後，務必使用 `admin` 帳號進入「系統後台」，重設所有人員的真實密碼！

---

## 📖 開發與維護指南

如果您是接手後續開發（如實作尚未開發的模組）的工程師，請務必先詳細閱讀：
1. 本地目錄內的 `app/static/dev_manual.md` **(開發說明書)**。
2. 開發手冊內載明了「三層架構分離 (Service Layer)」的強制規範，以及如何輕鬆讓「子模組的權限」自動掛載到後台 UI 的詳細 `Phase 2 Expansion Guide`。

如果您是系統營運方，想了解如何設定 Google API 備份或是新增店鋪與員工，請至系統登入 `admin` 後，點選右上角的 **《系統管理手冊》**。