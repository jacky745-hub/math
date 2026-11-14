from functools import wraps

from flask import Blueprint, flash, g, redirect, render_template, request, session, url_for

from src.extensions import db
from src.models import ROLE_RANK, User, get_settings

bp = Blueprint("auth", __name__)


def current_user():
    if "user" not in g:
        uid = session.get("uid")
        g.user = db.session.get(User, uid) if uid else None
    return g.user


def login_required(min_role="student"):
    def deco(fn):
        @wraps(fn)
        def wrapper(*a, **kw):
            u = current_user()
            if not u:
                flash("請先登入。")
                return redirect(url_for("auth.login", next=request.path))
            if u.rank < ROLE_RANK[min_role]:
                return render_template("message.html", title="權限不足", msg="您的身分無法使用這項功能。"), 403
            return fn(*a, **kw)
        return wrapper
    return deco


@bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        f = request.form
        username, pw = f.get("username", "").strip(), f.get("password", "")
        role = f.get("role", "student")
        err = None
        if len(username) < 3:
            err = "帳號至少 3 個字元。"
        elif len(pw) < 6:
            err = "密碼至少 6 個字元。"
        elif pw != f.get("password2", ""):
            err = "兩次輸入的密碼不一致。"
        elif User.query.filter_by(username=username).first():
            err = "這個帳號已有人使用，請換一個。"
        elif role == "teacher":
            code = get_settings().get("teacher_code", "")
            if not code or f.get("teacher_code", "") != code:
                err = "教師註冊碼不正確。（請向系統管理者索取；或先註冊為學生，再請管理者升級身分。）"
        elif role != "student":
            err = "管理者與 admin 身分須由 admin 於後台指派。"
        if err:
            flash(err)
            return render_template("register.html", form=f)
        u = User(username=username, name=f.get("name", "").strip(), role=role, school=f.get("school", "").strip(),
                 class_name=f.get("class_name", "").strip(), seat_no=f.get("seat_no", "").strip())
        u.set_password(pw)
        db.session.add(u)
        db.session.commit()
        session["uid"] = u.id
        flash("註冊成功，歡迎使用！")
        return redirect(url_for("front.home"))
    return render_template("register.html", form={})


@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        u = User.query.filter_by(username=request.form.get("username", "").strip()).first()
        if u and u.check_password(request.form.get("password", "")):
            session.clear()
            session["uid"] = u.id
            nxt = request.args.get("next", "")
            return redirect(nxt if nxt.startswith("/") and not nxt.startswith("//") else url_for("front.home"))
        flash("帳號或密碼不正確。")
    return render_template("login.html")


@bp.route("/logout", methods=["POST", "GET"])
def logout():
    session.clear()
    flash("已登出。")
    return redirect(url_for("auth.login"))


@bp.route("/account", methods=["GET", "POST"])
@login_required()
def account():
    u = current_user()
    if request.method == "POST":
        f = request.form
        u.name, u.school = f.get("name", "").strip(), f.get("school", "").strip()
        u.class_name, u.seat_no = f.get("class_name", "").strip(), f.get("seat_no", "").strip()
        if f.get("new_password"):
            if not u.check_password(f.get("old_password", "")):
                flash("目前密碼不正確，密碼未變更。")
            elif len(f["new_password"]) < 6:
                flash("新密碼至少 6 個字元。")
            else:
                u.set_password(f["new_password"])
                flash("密碼已更新。")
        db.session.commit()
        flash("資料已儲存。")
        return redirect(url_for("auth.account"))
    return render_template("account.html")
