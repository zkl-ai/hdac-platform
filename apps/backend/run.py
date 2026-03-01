from app import create_app
from app.extensions import db, socketio
from app.models.device import Device
from app.init_db import init_db
import os

app = create_app()

if __name__ == '__main__':
    with app.app_context():
        try:
            db.create_all()
            init_db()
        except Exception as e:
            print(f"[WARN] 数据库初始化失败：{e}")
            print("[WARN] 服务继续启动，但数据库不可用。请检查 MySQL 或设置 DATABASE_URL 为可用的数据源。")
    port = int(os.getenv("PORT", "5088"))
    socketio.run(app, host='0.0.0.0', port=port, debug=True, allow_unsafe_werkzeug=True)
