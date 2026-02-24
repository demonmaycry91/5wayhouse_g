#!/bin/bash

# 這個腳本會自動化專案的啟動流程，包含解決 macOS 特定的依賴問題與 Redis 服務。
# 請注意，部分手動步驟仍需要您自行完成。

echo "=========================================="
echo "    開始執行 5 Way House 自動初始化腳本"
echo "=========================================="

# ==========================================
# 0. 增強版 Homebrew 偵測
# ==========================================
if command -v brew &> /dev/null; then
    BREW_CMD="brew"
elif [ -x "/opt/homebrew/bin/brew" ]; then
    BREW_CMD="/opt/homebrew/bin/brew" # Apple 晶片預設路徑
elif [ -x "/usr/local/bin/brew" ]; then
    BREW_CMD="/usr/local/bin/brew"   # Intel 晶片預設路徑
else
    BREW_CMD=""
fi

# ==========================================
# 1. 尋找或安裝 Python 3.12
# ==========================================
echo "--> 1. 尋找合適的 Python 版本並建立虛擬環境..."

if command -v python3.12 &> /dev/null; then
    PYTHON_CMD="python3.12"
elif command -v python3.11 &> /dev/null; then
    PYTHON_CMD="python3.11"
elif command -v python3.10 &> /dev/null; then
    PYTHON_CMD="python3.10"
else
    echo "⚠️ 找不到建議的 Python 版本 (3.10~3.12)。"
    
    if [ -n "$BREW_CMD" ]; then
        echo "--> 準備使用 Homebrew 自動安裝 Python 3.12..."
        $BREW_CMD install python@3.12
        
        # 安裝完成後，找出 python3.12 的正確路徑
        if [ -x "/opt/homebrew/bin/python3.12" ]; then
            PYTHON_CMD="/opt/homebrew/bin/python3.12"
        elif [ -x "/usr/local/bin/python3.12" ]; then
            PYTHON_CMD="/usr/local/bin/python3.12"
        elif command -v python3.12 &> /dev/null; then
            PYTHON_CMD="python3.12"
        else
            echo "❌ 安裝似乎完成了，但找不到 python3.12 的執行檔路徑，請手動確認安裝狀況。"
            exit 1
        fi
        echo "✅ 成功找到 Python 3.12: $PYTHON_CMD"
    else
        echo "❌ 你的 Mac 尚未安裝 Homebrew，無法進行自動安裝。"
        echo "請先打開終端機，貼上以下指令來安裝 Homebrew："
        echo '/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"'
        exit 1
    fi
fi

# ==========================================
# 1.5 安裝系統依賴庫 (WeasyPrint 依賴與 Redis)
# ==========================================
if [ -n "$BREW_CMD" ]; then
    echo "--> 1.5 檢查並安裝系統依賴 (pango, glib, fontconfig, redis)..."
    # 這行會自動檢查並安裝缺少的系統庫與 Redis
    $BREW_CMD install pango glib fontconfig redis
    
    echo "--> 啟動 Redis 背景服務..."
    # 這行確保 Redis 在背景運行，即使重開機也會自動執行
    $BREW_CMD services start redis
    echo "✅ 系統依賴與 Redis 服務設定完成！"
fi

# ==========================================
# 2. 建立並啟用 Python 虛擬環境
# ==========================================
# 確保之前的舊虛擬環境被刪除，以免發生衝突或殘留壞掉的檔案
if [ -d ".venv" ]; then
    echo "🧹 刪除舊的 .venv 虛擬環境..."
    rm -rf .venv
fi

$PYTHON_CMD -m venv .venv
VENV_PYTHON=.venv/bin/python
VENV_FLASK=.venv/bin/flask

if [ ! -f "$VENV_PYTHON" ]; then
    echo "❌ 錯誤：虛擬環境建立失敗。終止腳本。"
    exit 1
fi
echo "✅ 成功建立虛擬環境。"

# ==========================================
# 3. 安裝 pip-tools 並更新 pip
# ==========================================
echo "--> 2. 安裝 pip-tools 並更新 pip..."
$VENV_PYTHON -m pip install pip-tools
$VENV_PYTHON -m pip install --upgrade pip

# ==========================================
# 4. 編譯並安裝所有依賴套件
# ==========================================
echo "--> 3. 編譯並安裝所有依賴套件..."
$VENV_PYTHON -m piptools compile requirements.in
$VENV_PYTHON -m pip install -r requirements.txt
$VENV_PYTHON -m piptools sync

# ==========================================
# 5. 設定 FLASK_APP 環境變數
# ==========================================
echo "--> 4. 設定 FLASK_APP 環境變數..."
export FLASK_APP=run.py
export OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES
echo "FLASK_APP 已設定為 run.py"

# ==========================================
# 6. 執行資料庫遷移
# ==========================================
echo "--> 5. 執行資料庫遷移..."
echo "警告：這將會刪除現有的資料庫檔案和遷移資料夾，請確認！"
rm -f instance/app.db
rm -rf migrations
$VENV_FLASK db init
$VENV_FLASK db migrate -m "Initial migration"
$VENV_FLASK db upgrade

# ==========================================
# 7. 初始化後台角色與管理員
# ==========================================
echo "--> 6. 初始化後台角色..."
$VENV_FLASK auth init-roles

echo "--> 7. 建立預設的管理員帳號..."
$VENV_FLASK auth create-user root password --role Admin

echo "
=====================================================
🎉 專案初始化完成！🎉

系統依賴、Redis 服務、WeasyPrint 與資料庫皆已設定完畢。
請手動完成以下步驟：
1. 啟動 Flask 伺服器：
   輸入 'source .venv/bin/activate' 後執行 'flask run'
2. 在另一個終端機中，啟動 RQ worker：
   輸入 'source .venv/bin/activate' 後執行 'rq worker cashier-tasks'
3. 將 Google API 憑證 (client_secret.json 和 token.json) 
   放置到 instance/ 資料夾中。
=====================================================
"