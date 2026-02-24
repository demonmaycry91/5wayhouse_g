# 5 Way House 結帳與報表系統

這是一個為 5 Way House 開發的 Web 應用程式，主要提供結帳 POS 介面、資料庫管理，並整合了 Google API (Drive/Sheets) 進行資料自動備份，以及使用 WeasyPrint 生成 PDF 報表。專案同時使用 Redis 與 RQ (Redis Queue) 來處理耗時的背景任務。

---

## 💻 系統需求

* **作業系統**：推薦使用 macOS 或 Linux。
  * *Windows 使用者強烈建議安裝 WSL (Windows Subsystem for Linux) 並在 Ubuntu 環境下運行，以完整支援 Redis 背景服務。*
* **必備工具**：
  * **macOS**：請確保已安裝 [Homebrew](https://brew.sh/)（安裝腳本會自動偵測並調用）。

---

## 🚀 專案安裝與初始化 (Setup)

我們提供了一鍵式的自動化設定腳本 `setup.sh`。該腳本會自動幫您處理 Python 3.12 安裝、Redis 背景服務、WeasyPrint 系統依賴庫（pango, glib, fontconfig）、虛擬環境建置以及資料庫遷移。

### 步驟 1：執行設定腳本
請開啟終端機 (Terminal)，進入專案根目錄，並依序執行以下指令：

```bash
# 給予腳本執行權限
chmod +x setup.sh

# 執行自動化安裝 (可能需要數分鐘下載依賴套件)
./setup.sh
```

### 步驟 2：配置 Google API 憑證
為確保自動備份功能正常運作，請手動設定 Google 憑證：
1. 進入專案根目錄，檢查是否有 `instance/` 資料夾（若無請自行建立）。
2. 將您的 Google API 憑證檔案放入該資料夾，並確保檔名正確：
   * `instance/client_secret.json`
   * `instance/token.json` (若有歷史授權金鑰)

---

## 🟢 啟動系統服務 (Start)

專案需要同時運行 **Flask Web 伺服器** (前景) 與 **RQ 背景任務處理器** (背景)。我們提供了 `start.sh` 腳本來一鍵啟動這兩個服務。

### 步驟 1：賦予啟動腳本權限 (僅首次需要)
```bash
chmod +x start.sh
```

### 步驟 2：一鍵啟動服務
```bash
./start.sh
```
執行後，您會看到 Flask 伺服器與 RQ Worker 同時啟動的提示訊息。此時即可打開瀏覽器訪問系統 (預設為 `http://127.0.0.1:5000`)。

### 步驟 3：安全關閉服務
當您想停止伺服器時，只需在該終端機視窗中按下鍵盤上的 **`Ctrl + C`**。
腳本會自動且安全地同時關閉 Flask 與背景的 RQ Worker，避免資源佔用。

---

## 🔑 預設管理員帳號

資料庫初始化完成後，系統會自動建立一組最高權限的管理員帳號：
* **帳號**：`root`
* **密碼**：`password`

⚠️ **安全性警告**：請於系統部署或首次登入後，盡速至後台修改預設密碼！