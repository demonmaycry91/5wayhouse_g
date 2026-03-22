from app import create_app
import os

app = create_app()

if __name__ == '__main__':
    # 改從 config 或環境變數取得 debug 設定
    is_debug = app.config.get('DEBUG', False)
    # 本地開發預設允許外部連線
    app.run(host='0.0.0.0', debug=is_debug)