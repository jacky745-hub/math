import csv
import io
import json
import os
import zipfile

from flask import (Blueprint, Response, current_app, flash, redirect, render_template, request, send_file, url_for)

from src import ai_engine, services
from src.extensions import db
from src.models import (DEFAULT_SETTINGS, ROLE_RANK, ROLES, AnalysisCache, Contribution, MapScore, Member, Setting,
                        Submission, TextDoc, User, get_settings)
from src.routes.auth import current_user, login_required

bp = Blueprint("admin", __name__, url_prefix="/admin")


@bp.route("/")
@login_required("teacher")
def index():
    stats = {"users": User.query.count(), "subs": Submission.query.count(),
             "scored": Submission.query.filter_by(status="scored").count(),
             "pending": Submission.query.filter(Submission.status != "scored").count(),
             "texts": TextDoc.query.count(), "members": Member.query.count()}
    subs = Submission.query.order_by(Submission.created_at.desc()).limit(200).all()
    return render_template("admin_index.html", stats=stats, subs=subs, ai_ready=ai_engine.available(), model=ai_engine.MODEL)


# ------------------------------------------------------------ 使用者管理
@bp.route("/users")
@login_required("manager")
def users():
    return render_template("admin_users.html", users=User.query.order_by(User.role.desc(), User.username).all(), ROLES=ROLES)


@bp.route("/users/<int:uid>/delete", methods=["POST"])
@login_required("manager")
def user_delete(uid):
    me, u = current_user(), db.session.get(User, uid)
    if not u or u.id == me.id:
        flash("無法刪除這個帳號。")
    elif me.role != "admin" and u.rank >= me.rank:
        flash("只能剔除身分低於自己的帳號（admin 可剔除任何人）。")
    elif u.role == "admin" and User.query.filter_by(role="admin").count() <= 1:
        flash("系統至少要保留一位 admin。")
    else:
        Submission.query.filter_by(created_by=u.id).update({"created_by": None})
        TextDoc.query.filter_by(created_by=u.id).update({"created_by": None})
        db.session.delete(u)
        db.session.commit()
        flash(f"已剔除帳號 {u.username}（其上傳的概念圖與評分紀錄仍保留供研究使用）。")
    return redirect(url_for("admin.users"))


@bp.route("/users/<int:uid>/role", methods=["POST"])
@login_required("admin")
def user_role(uid):
    u, role = db.session.get(User, uid), request.form.get("role")
    if u and role in ROLES:
        if u.role == "admin" and role != "admin" and User.query.filter_by(role="admin").count() <= 1:
            flash("系統至少要保留一位 admin。")
        else:
            u.role = role
            db.session.commit()
            flash(f"已將 {u.username} 的身分改為 {u.role_label}。")
    return redirect(url_for("admin.users"))


@bp.route("/users/<int:uid>/reset", methods=["POST"])
@login_required("manager")
def user_reset(uid):
    me, u = current_user(), db.session.get(User, uid)
    pw = request.form.get("password", "")
    if not u or (me.role != "admin" and u.rank >= me.rank) or len(pw) < 6:
        flash("無法重設（密碼至少 6 個字元，且只能重設身分低於自己的帳號）。")
    else:
        u.set_password(pw)
        db.session.commit()
        flash(f"已重設 {u.username} 的密碼。")
    return redirect(url_for("admin.users"))


# ------------------------------------------------------------ 小組資料
@bp.route("/submission/<int:sid>/delete", methods=["POST"])
@login_required("teacher")
def sub_delete(sid):
    sub = db.session.get(Submission, sid)
    if sub:
        db.session.delete(sub)
        db.session.commit()
        flash("已刪除該筆小組資料（原始檔案仍保留於伺服器）。")
    return redirect(url_for("admin.index"))


def _template(sub):
    blank = {"root": "", "nodes": [], "relations": [], "examples": [], "cross_links": [], "rejected": [],
             "hierarchy": {"chain": [], "note": ""},
             "comments": {"relations": "", "hierarchy": "", "examples": "", "cross_links": ""},
             "strengths": [], "weaknesses": [], "conflicts": []}
    inv = {"title": "", "root": "", "concepts": [], "reference": {"relations": 0, "levels": 0, "cross_links": 0, "examples": 0, "items": []},
           "standard_score": 0, "cross_hints": [], "analogy": ""}
    return {"inventory": services.cache_get(services.inventory_key(sub.text)) or inv,
            "collab": services.cache_get(services.map_key(sub)) or blank,
            "individual": {m.seat_no: services.cache_get(services.map_key(sub, m)) or blank for m in sub.members}}


@bp.route("/submission/<int:sid>/analysis", methods=["GET", "POST"])
@login_required("teacher")
def analysis(sid):
    """判讀匯入／檢視／修正：教師可下載判讀 JSON、修改後匯入，系統據此重新計分。"""
    sub = db.session.get(Submission, sid)
    if not sub:
        return render_template("message.html", title="找不到資料", msg="這筆小組資料不存在。"), 404
    if request.method == "POST":
        raw = request.form.get("bundle", "")
        up = request.files.get("bundle_file")
        if up and up.filename:
            raw = up.read().decode("utf-8-sig", errors="ignore")
        try:
            data = json.loads(raw)
            if not isinstance(data, dict) or "collab" not in data or "individual" not in data:
                raise ValueError("JSON 需包含 inventory、collab、individual 三個部分。")
            missing = [m.seat_no for m in sub.members if m.seat_no not in data["individual"]]
            if missing:
                raise ValueError("缺少座號 " + "、".join(missing) + " 的個人圖判讀。")
            who = f"人工判讀:{current_user().username}"
            if data.get("inventory"):
                services.cache_put(services.inventory_key(sub.text), "inventory", data["inventory"], who, overwrite=True)
            services.cache_put(services.map_key(sub), "collab", data["collab"], who, overwrite=True)
            for m in sub.members:
                services.cache_put(services.map_key(sub, m), "individual", data["individual"][m.seat_no], who, overwrite=True)
        except (ValueError, json.JSONDecodeError) as e:
            flash(f"匯入未完成：{e}")
            return render_template("admin_analysis.html", sub=sub, bundle=raw)
        services.score_submission(sub.id, use_ai=False)
        flash("判讀已匯入並完成計分。")
        return redirect(url_for("front.submission", sid=sid))
    return render_template("admin_analysis.html", sub=sub, bundle=json.dumps(_template(sub), ensure_ascii=False, indent=1))


@bp.route("/submission/<int:sid>/analysis.json")
@login_required("teacher")
def analysis_download(sid):
    sub = db.session.get(Submission, sid)
    body = json.dumps(_template(sub), ensure_ascii=False, indent=1)
    return Response(body, mimetype="application/json",
                    headers={"Content-Disposition": f"attachment; filename=analysis_{sid}.json"})


# ------------------------------------------------------------ 設定
@bp.route("/settings", methods=["GET", "POST"])
@login_required("manager")
def settings():
    if request.method == "POST":
        try:
            for k in DEFAULT_SETTINGS:
                v = request.form.get(k, "").strip()
                if k not in ("teacher_code",) and v != "":
                    float(v)
                row = db.session.get(Setting, k) or Setting(key=k)
                row.value = v
                db.session.add(row)
            db.session.commit()
            flash("設定已儲存。（新設定在下次評分或按「重新評分」時生效）")
        except ValueError:
            db.session.rollback()
            flash("權重與係數請填數字。")
        return redirect(url_for("admin.settings"))
    return render_template("admin_settings.html", s=get_settings(), ai_ready=ai_engine.available(), model=ai_engine.MODEL)


# ------------------------------------------------------------ 匯出
def _tables():
    subs = Submission.query.order_by(Submission.id).all()
    t = {}
    t["小組"] = [["小組編號", "校名", "班級", "組別", "文本標題", "組員人數", "狀態", "判讀引擎", "協作圖原始分", "協作圖總分(含補登)",
                  "個人圖平均", "標準分數", "補登係數", "上傳者", "上傳時間", "評分時間", "協作圖檔名", "協作圖SHA256"]]
    t["個人與協作圖評分"] = [["小組編號", "校名", "班級", "組別", "圖別", "座號", "姓名", "顏色", "關係數", "關係分", "階層數", "階層分",
                          "例子數", "例子分", "交叉連結數", "交叉連結分", "總分", "回饋", "檔名", "檔案SHA256", "上傳時間"]]
    t["評分細節"] = [["小組編號", "校名", "班級", "圖別", "座號", "姓名", "項目", "得分細節", "得分", "說明"]]
    t["貢獻值"] = [["小組編號", "校名", "班級", "組別", "座號", "姓名", "顏色", "個人圖分數", "D1概念數量", "D2關係鏈品質", "D3層次構建",
                  "D4交叉創新", "D5實例準確性", "協作個人貢獻分數", "協作效益加成", "公式一(%)", "公式二(%)", "公式三(%)", "協作類型",
                  "學習路徑", "協作圖親筆內容", "圈選認同", "補登內容", "公式一回饋", "公式二回饋", "公式三回饋", "分層指導與路徑", "上傳時間"]]
    for s in subs:
        sm = s.summary
        t["小組"].append([s.id, s.school, s.class_name, s.group_name, s.text.title if s.text else "", len(s.members), s.status,
                          s.engine, sm.get("T_raw", ""), sm.get("T_adj", ""), sm.get("P_mean", ""), sm.get("standard", ""),
                          sm.get("supplement_coef", ""), s.creator.username if s.creator else "", _dt(s.created_at),
                          _dt(s.scored_at), s.collab_name, s.collab_sha])
        for sc in sorted(s.scores, key=lambda x: (x.map_type != "collab", x.member.order if x.member else 0)):
            m = sc.member
            kind = "協作圖" if sc.map_type == "collab" else "個人圖"
            t["個人與協作圖評分"].append([s.id, s.school, s.class_name, s.group_name, kind, m.seat_no if m else "", m.name if m else "",
                                    m.color if m else "", sc.relations_n, sc.relations_pts, sc.hierarchy_n, sc.hierarchy_pts,
                                    sc.examples_n, sc.examples_pts, sc.cross_n, sc.cross_pts, sc.total, sc.feedback,
                                    m.file_name if m else s.collab_name, m.file_sha if m else s.collab_sha, _dt(s.created_at)])
            for row in sc.detail:
                t["評分細節"].append([s.id, s.school, s.class_name, kind, m.seat_no if m else "", m.name if m else "",
                                  row["項目"], row["得分細節"], row["得分"], row["說明"]])
        for c in sorted(s.contributions, key=lambda x: x.member.order):
            m, d = c.member, c.detail
            au, su = d.get("authored", {}), d.get("supplement", {})
            t["貢獻值"].append([s.id, s.school, s.class_name, s.group_name, m.seat_no, m.name, m.color, c.individual_score,
                              c.d_concepts, c.d_relations, c.d_hierarchy, c.d_cross, c.d_examples, c.collab_score, c.bonus,
                              c.f1, c.f2, c.f3, c.role_type, c.path,
                              "；".join(au.get("nodes", []) + au.get("relations", []) + au.get("examples", []) + au.get("cross", [])),
                              "；".join(d.get("rings", [])),
                              "；".join(su.get("relations", []) + su.get("examples", []) + su.get("cross", [])),
                              c.feedback_f1, c.feedback_f2, c.feedback_f3, c.feedback_guidance, _dt(s.created_at)])
    t["使用者"] = [["編號", "帳號", "姓名", "身分", "校名", "班級", "座號", "註冊時間"]] + \
        [[u.id, u.username, u.name, u.role_label, u.school, u.class_name, u.seat_no, _dt(u.created_at)] for u in User.query.order_by(User.id)]
    return t


def _dt(d):
    return d.strftime("%Y-%m-%d %H:%M:%S") if d else ""


EXPORTS = {"groups": "小組", "scores": "個人與協作圖評分", "details": "評分細節", "contributions": "貢獻值", "users": "使用者"}


@bp.route("/export")
@login_required("teacher")
def export_page():
    return render_template("admin_export.html", EXPORTS=EXPORTS)


@bp.route("/export/<kind>.csv")
@login_required("teacher")
def export_csv(kind):
    if kind not in EXPORTS or (kind == "users" and current_user().rank < ROLE_RANK["manager"]):
        return render_template("message.html", title="無法匯出", msg="沒有這個資料表，或權限不足。"), 404
    buf = io.StringIO()
    csv.writer(buf).writerows(_tables()[EXPORTS[kind]])
    return Response("﻿" + buf.getvalue(), mimetype="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f"attachment; filename=conceptmap_{kind}.csv"})


@bp.route("/export/all.xlsx")
@login_required("teacher")
def export_xlsx():
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font
    wb = Workbook()
    wb.remove(wb.active)
    tables = _tables()
    if current_user().rank < ROLE_RANK["manager"]:
        tables.pop("使用者")
    for name, rows in tables.items():
        ws = wb.create_sheet(name)
        for r in rows:
            ws.append(r)
        for c in ws[1]:
            c.font = Font(bold=True)
        ws.freeze_panes = "A2"
        for col in ws.columns:
            width = min(60, max(10, max(len(str(c.value or "").split("\n")[0]) for c in col[:50]) * 1.8))
            ws.column_dimensions[col[0].column_letter].width = width
            for c in col:
                c.alignment = Alignment(wrap_text=True, vertical="top")
    out = io.BytesIO()
    wb.save(out)
    out.seek(0)
    return send_file(out, download_name="conceptmap_all.xlsx", as_attachment=True,
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


@bp.route("/export/files.zip")
@login_required("teacher")
def export_files():
    """所有學生上傳的概念圖原始檔，依 小組/座號 命名打包。"""
    out = io.BytesIO()
    root = current_app.config["UPLOAD_DIR"]
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        seen = set()

        def add(rel, arc):
            full = os.path.join(root, rel) if rel else ""
            if rel and os.path.exists(full) and arc not in seen:
                seen.add(arc)
                z.write(full, arc)
        for s in Submission.query.order_by(Submission.id):
            base = f"{s.id:04d}_{s.school}_{s.class_name}_{s.group_name}".rstrip("_")
            add(s.collab_path, f"{base}/協作圖_{s.collab_name}")
            if s.text and s.text.file_path:
                add(s.text.file_path, f"{base}/文本_{s.text.file_name}")
            for m in s.members:
                add(m.file_path, f"{base}/個人圖_座號{m.seat_no}_p{m.page}_{m.file_name}")
    out.seek(0)
    return send_file(out, download_name="conceptmap_files.zip", as_attachment=True, mimetype="application/zip")


@bp.route("/export/analysis.json")
@login_required("teacher")
def export_analysis():
    rows = [{"key": r.key, "kind": r.kind, "engine": r.engine, "created_at": _dt(r.created_at), "data": r.data}
            for r in AnalysisCache.query.all()]
    return Response(json.dumps(rows, ensure_ascii=False, indent=1), mimetype="application/json",
                    headers={"Content-Disposition": "attachment; filename=conceptmap_analysis.json"})
