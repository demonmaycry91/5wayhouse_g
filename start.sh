#!/bin/bash

echo "=========================================="
echo "    啟動 5 Way House 系統服務"
echo "=========================================="

# 1. 檢查虛擬環境是否存在
if [ ! -d ".venv" ]; then
    echo "❌ 找不到虛擬環境 (.venv)！請先執行 ./setup.sh 來初始化專案。"
    exit 1
fi

# 2. 啟用虛擬環境
source .venv/bin/activate

# 3. 啟動 RQ Worker (在背景執行)
echo "啟動 RQ worker (背景服務)..."
rq worker cashier-tasks &
# 紀錄 RQ worker 的 Process ID (PID)，以便等一下可以自動關閉它
RQ_PID=$!

# 4. 啟動 Flask 伺服器
echo "啟動 Flask Web 伺服器..."
export FLASK_APP=run.py
export OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES

# 5. 設定自動關閉機制 (Trap)
# 當你在終端機按下 Ctrl + C 時，會觸發這個機制，自動殺掉背景的 RQ worker
trap "echo -e '\n\n🛑 正在關閉系統服務...'; kill $RQ_PID 2>/dev/null; echo '✅ 服務已完全關閉。'; exit" SIGINT SIGTERM
# 在前景執行 Flask
flask run

# 等待背景進程
wait