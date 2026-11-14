"""國中生協作概念圖評分回饋系統 — Flask 進入點。

資料庫初始化（重點）：
  1. 全系統只有 src/extensions.py 的一個 `db = SQLAlchemy()`。
  2. create_app() 內先設定 SQLALCHEMY_DATABASE_URI，再呼叫「一次」 db.init_app(app)。
  3. 建表與預設帳號都在 `with app.app_context():` 內完成。
  4. 背景執行緒一律以同一個 app 物件 push app_context 後才使用 db。
前端由 Flask 同源提供（無 Vite 開發伺服器），因此不存在 allowedHosts / 跨網域 / 連不到 localhost 的問題。
"""
import os
import secrets

from flask import Flask, render_template, request, session
from werkzeug.middleware.proxy_fix import ProxyFix

from src.extensions import db

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def create_app(config=None):
    app = Flask(__name__, static_folder="static", template_folder="templates")
    data_dir = os.environ.get("CM_DATA_DIR", os.path.join(BASE_DIR, "instance"))
    app.config.update(
        SECRET_KEY=os.environ.get("SECRET_KEY", ""),
        SQLALCHEMY_DATABASE_URI=os.environ.get("DATABASE_URL", ""),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        SQLALCHEMY_ENGINE_OPTIONS={"pool_pre_ping": True},
        MAX_CONTENT_LENGTH=200 * 1024 * 1024,
        DATA_DIR=data_dir,
        SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax",
    )
    if config:
        app.config.update(config)
    data_dir = app.config["DATA_DIR"]
    os.makedirs(data_dir, exist_ok=True)
    app.config.setdefault("UPLOAD_DIR", os.path.join(data_dir, "uploads"))
    os.makedirs(app.config["UPLOAD_DIR"], exist_ok=True)
    if not app.config["SQLALCHEMY_DATABASE_URI"]:
        app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.join(data_dir, "conceptmap.db")
    if app.config["SQLALCHEMY_DATABASE_URI"].startswith("postgres://"):  # Render/Heroku 舊式寫法
        app.config["SQLALCHEMY_DATABASE_URI"] = app.config["SQLALCHEMY_DATABASE_URI"].replace("postgres://", "postgresql://", 1)
    if not app.config["SECRET_KEY"]:  # 未設定時產生並保存，重啟後登入狀態不會失效
        key_file = os.path.join(data_dir, "secret_key")
        if not os.path.exists(key_file):
            with open(key_file, "w") as f:
                f.write(secrets.token_hex(32))
        app.config["SECRET_KEY"] = open(key_file).read().strip()

    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)  # 反向代理／任何對外網域皆可

    db.init_app(app)  # ← 唯一一次綁定

    from src import models  # noqa: F401  確保所有資料表已註冊
    from src.routes.admin import bp as admin_bp
    from src.routes.auth import bp as auth_bp, current_user
    from src.routes.front import bp as front_bp
    app.register_blueprint(auth_bp)
    app.register_blueprint(front_bp)
    app.register_blueprint(admin_bp)

    with app.app_context():
        db.create_all()
        _ensure_admin(app)

    @app.context_processor
    def inject():
        if "csrf" not in session:
            session["csrf"] = secrets.token_hex(16)
        return {"me": current_user(), "csrf": session["csrf"], "ROLE_LABEL": models.ROLE_LABEL}

    @app.before_request
    def csrf_protect():
        if request.method == "POST" and not app.config.get("TESTING"):
            if request.form.get("csrf") != session.get("csrf"):
                return render_template("message.html", title="頁面已過期",
                                       msg="為了安全，請回到上一頁重新整理後再操作一次。"), 400

    @app.errorhandler(404)
    def not_found(e):
        return render_template("message.html", title="找不到頁面", msg="這個網址不存在，請從選單重新進入。"), 404

    @app.errorhandler(413)
    def too_large(e):
        return render_template("message.html", title="檔案太大", msg="單次上傳總大小上限為 200 MB，請壓縮或分次上傳。"), 413

    @app.errorhandler(500)
    def server_error(e):
        db.session.rollback()
        return render_template("message.html", title="系統忙碌中",
                               msg="剛才的操作沒有完成，已上傳的資料不受影響。請回上一頁再試一次。"), 500

    @app.get("/healthz")
    def healthz():
        db.session.execute(db.text("SELECT 1"))
        return {"ok": True}

    return app


def _ensure_admin(app):
    from src.models import User
    if User.query.filter_by(role="admin").first():
        return
    username = os.environ.get("ADMIN_USERNAME", "admin")
    password = os.environ.get("ADMIN_PASSWORD")
    generated = not password
    if generated:
        password = secrets.token_urlsafe(9)
    u = User(username=username, name="系統管理者", role="admin")
    u.set_password(password)
    db.session.add(u)
    db.session.commit()
    if generated:
        path = os.path.join(app.config["DATA_DIR"], "admin_initial_password.txt")
        with open(path, "w") as f:
            f.write(f"帳號：{username}\n密碼：{password}\n（登入後請至「我的帳號」修改密碼並刪除此檔）\n")
        print(f"[concept-map] 已建立 admin 帳號，初始密碼寫入 {path}")


app = None
if os.environ.get("CM_NO_AUTOCREATE") != "1":
    app = create_app()

if __name__ == "__main__":
    (app or create_app()).run(host="0.0.0.0", port=int(os.environ.get("PORT", 5001)), debug=False)
