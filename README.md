# 🏪 5 Way House (五味屋) 營運與結帳整合系統 

本系統是一個專為五味屋及其相關據點開發的現代化 Web 應用程式。我們將實體店鋪收銀 POS、倉庫物流、工坊登記、志工排班與住宿管理整合成單一 Web 入口。

系統全面採用 **Docker 容器化架構**，確保無論在 Windows、macOS 或是 Linux 伺服器上，都能達到「零門檻、一鍵部署」的順暢體驗。您完全不需要手動安裝 Python 或設定資料庫，只要有 Docker 即可快速運行。

---

## 🚀 Docker 安裝與運行指南 (詳細步驟)

請依序跟著以下步驟進行，即可在 3~5 分鐘內將整套系統於您的電腦或伺服器上運行起來。

### 🛠️ 步驟 1：安裝 Docker Desktop
若您的電腦尚未安裝 Docker，請依據您的作業系統前往官網下載並安裝：
👉 **[下載 Docker Desktop](https://www.docker.com/products/docker-desktop/)**

*(🐰 溫馨提示：Windows 用戶安裝時請同意開啟 WSL 2 功能；安裝完畢後請啟動 Docker Desktop，確保右下角常駐列有出現 Docker 小鯨魚圖示且顯示「Engine Running」。)*

### 📥 步驟 2：取得專案程式碼
請打開您的終端機（Mac 為 `Terminal`，Windows 請開啟 `命令提示字元`、`PowerShell` 或 `Git Bash`），然後依序輸入：

```bash
# 讓終端機走到桌面 (以桌面為例)
cd Desktop

# 將專案下載到您的電腦上
git clone https://github.com/demonmaycry91/5wayhouse_g.git

# 進入專案資料夾
cd 5wayhouse_g
```

### ⚙️ 步驟 3：配置環境變數密碼檔 (.env)
系統需要一組密碼與環境設定才能啟動。我們已經為您準備好了範本檔案：

**對於 Mac / Linux / Windows Git Bash 用戶：**
可以直接在終端機輸入：
```bash
cp .env.example .env
```
*(請打開 `.env` 檔案，尋找 `SECRET_KEY=` 這一行，並在等號後面隨便輸入一串無意義的英文數字亂碼，例如 `SECRET_KEY=fk39v8h4b1nv89`，這會保護您的網站資安。)*

**對於 Windows 一般用戶：**
請直接打開資料夾，找到 `.env.example` 這個檔案，將它**重新命名**為 `.env` 即可（並打開編輯 `SECRET_KEY`）。

### 🐳 步驟 4：一鍵編譯與啟動伺服器
現在，讓 Docker 發揮它的魔法。請在終端機（確保您還在 `5wayhouse_g` 資料夾內）輸入以下指令：

```bash
docker-compose --env-file .env up -d --build
```

**這個過程會發生什麼事？**
1. Docker 會開始下載 Python 執行環境以及系統所需的所有套件（如 Redis、OCR 辨識工具、PDF 生成器）。第一次執行可能需花費 3~5 分鐘，請耐心等候。
2. 系統內建的 `entrypoint.sh` 腳本會被自動觸發。
3. 它會自動幫您**建立資料庫**、**寫入最新版本的權限架構**。
4. 它會自動為您生成一組預設的測試帳號。

### 🎉 步驟 5：登入系統
當終端機畫面跑完，回到命令提示字元時，代表伺服器已經成功在背景運作！

請打開您的網頁瀏覽器（如 Chrome 或 Edge），在網址列輸入：
👉 **http://localhost:5001**

系統已自動幫您建置好最高權限的管理員帳號，請使用以下資訊登入：
- **帳號**：`admin`
- **密碼**：`123456`

*(⚠️ 登入後，建議您前往「系統後台管理 > 使用者管理」，修改 admin 帳號的密碼。)*

---

## 🛑 常用維護與關閉指令

若您想關閉系統，或查看系統運行狀態，請在終端機使用以下指令：

```bash
# 安全關閉伺服器與資料庫 (不會刪除資料)
docker-compose down

# 重新啟動伺服器 (若電腦重開機後想再次開啟系統)
docker-compose up -d

# 查看網站防護與連線日誌 (若遇到 500 錯誤，可在此追蹤問題)
docker-compose logs -f web

# 查看背景自動備份任務日誌
docker-compose logs -f worker
```

一旦您完成上述的 Docker 部署，其餘所有的人員新增、據點擴充、報表查詢、以及連接 Google 雲端帳號備份，皆可直接使用 `admin` 帳號在「網頁的系統後台」中全圖形化操作，完全不需再碰觸終端機程式碼！