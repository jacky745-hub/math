import os

from flask import (Blueprint, current_app, flash, redirect, render_template, request, send_file, url_for)

from src import ai_engine, services
from src.extensions import db
from src.models import Member, Submission, TextDoc
from src.routes.auth import current_user, login_required

bp = Blueprint("front", __name__)


def can_view(u, sub):
    if u.rank >= 1 or sub.created_by == u.id:
        return True
    return bool(u.seat_no) and sub.class_name == u.class_name and sub.school == u.school and \
        any(m.seat_no == u.seat_no for m in sub.members)


def visible_submissions(u):
    q = Submission.query.order_by(Submission.created_at.desc())
    if u.rank >= 1:
        return q.all()
    return [s for s in q.all() if can_view(u, s)]


@bp.route("/")
def home():
    u = current_user()
    if not u:
        return render_template("landing.html")
    return render_template("home.html", subs=visible_submissions(u))


@bp.route("/upload", methods=["GET", "POST"])
@login_required()
def upload():
    u = current_user()
    texts = TextDoc.query.order_by(TextDoc.created_at.desc()).all()
    if request.method == "POST":
        f, files = request.form, request.files
        try:
            school, class_name = f.get("school", "").strip(), f.get("class_name", "").strip()
            if not school or not class_name:
                raise ValueError("請填寫校名與班級。")
            # ---- 文本：選既有 / 貼上 / 上傳檔案
            text = None
            if f.get("text_id"):
                text = db.session.get(TextDoc, int(f["text_id"]))
            content = f.get("text_content", "").strip()
            tfile = files.get("text_file")
            if text is None:
                if not content and not (tfile and tfile.filename):
                    raise ValueError("請選擇、貼上或上傳「概念圖文本」。")
                rel = name = ""
                if tfile and tfile.filename:
                    rel, name, digest = services.save_upload(tfile, "texts")
                    if not content and name.lower().endswith(".txt"):
                        content = open(os.path.join(current_app.config["UPLOAD_DIR"], rel), encoding="utf-8", errors="ignore").read()
                sha = services.sha256_bytes(" ".join(content.split()).encode()) if content else digest
                text = TextDoc.query.filter_by(sha256=sha).first()
                if not text:
                    text = TextDoc(title=f.get("text_title", "").strip() or (content[:20] if content else name),
                                   content=content, file_path=rel, file_name=name, sha256=sha, created_by=u.id)
                    db.session.add(text)
                    db.session.flush()
            # ---- 組員
            seats, names, colors = f.getlist("seat_no"), f.getlist("name"), f.getlist("color")
            pages, mfiles = f.getlist("page"), files.getlist("member_file")
            shared = files.get("shared_file")
            shared_saved = services.save_upload(shared, "maps") if shared and shared.filename else None
            rows = []
            for i, seat in enumerate(seats):
                seat = seat.strip()
                if not seat and not (names[i] if i < len(names) else "").strip():
                    continue
                if not seat:
                    raise ValueError(f"第 {i + 1} 位組員沒有填座號。")
                color = (colors[i] if i < len(colors) else "").strip()
                if not color:
                    raise ValueError(f"座號 {seat} 沒有填顏色。")
                mf = mfiles[i] if i < len(mfiles) else None
                if mf and mf.filename:
                    saved = services.save_upload(mf, "maps")
                elif shared_saved:
                    saved = shared_saved
                else:
                    raise ValueError(f"座號 {seat} 沒有上傳個人概念圖。")
                page = int(pages[i]) if i < len(pages) and str(pages[i]).isdigit() else 1
                rows.append((seat, (names[i] if i < len(names) else "").strip(), color, saved, page))
            if len(rows) < 2:
                raise ValueError("協作概念圖至少需要 2 位組員。")
            if len({r[0] for r in rows}) != len(rows):
                raise ValueError("組員座號重複了，請檢查。")
            if len({r[2] for r in rows}) != len(rows):
                raise ValueError("每位組員的顏色必須不同（幾位組員就有幾種顏色）。")
            cfile = files.get("collab_file")
            if not (cfile and cfile.filename):
                raise ValueError("請上傳小組的協作概念圖。")
            crel, cname, csha = services.save_upload(cfile, "maps")
            sub = Submission(school=school, class_name=class_name, group_name=f.get("group_name", "").strip(),
                             text_id=text.id, collab_path=crel, collab_name=cname, collab_sha=csha,
                             collab_page=int(f.get("collab_page") or 1), created_by=u.id,
                             status="pending", status_msg="檔案已存檔，等待判讀。")
            db.session.add(sub)
            db.session.flush()
            for i, (seat, name, color, saved, page) in enumerate(rows):
                db.session.add(Member(submission_id=sub.id, order=i, seat_no=seat, name=name, color=color,
                                      file_path=saved[0], file_name=saved[1], file_sha=saved[2], page=page))
            db.session.commit()
        except ValueError as e:
            db.session.rollback()
            flash(str(e))
            return render_template("upload.html", texts=texts, form=f)
        services.score_async(current_app._get_current_object(), sub.id)
        flash("上傳成功，所有檔案已存檔。")
        return redirect(url_for("front.submission", sid=sub.id))
    return render_template("upload.html", texts=texts, form={})


@bp.route("/submission/<int:sid>")
@login_required()
def submission(sid):
    u = current_user()
    sub = db.session.get(Submission, sid)
    if not sub or not can_view(u, sub):
        return render_template("message.html", title="無法檢視", msg="找不到這筆資料，或您沒有檢視權限。"), 404
    collab = next((s for s in sub.scores if s.map_type == "collab"), None)
    ind = {s.member_id: s for s in sub.scores if s.map_type == "individual"}
    con = {c.member_id: c for c in sub.contributions}
    # 學生只看自己的詳細回饋；教師以上看全組
    only = None
    if u.rank == 0 and u.seat_no and any(m.seat_no == u.seat_no for m in sub.members):
        only = u.seat_no
    return render_template("submission.html", sub=sub, collab=collab, ind=ind, con=con, only=only,
                           ai_ready=ai_engine.available())


@bp.route("/submission/<int:sid>/rescore", methods=["POST"])
@login_required()
def rescore(sid):
    sub = db.session.get(Submission, sid)
    if not sub or not can_view(current_user(), sub):
        return render_template("message.html", title="無法操作", msg="找不到這筆資料。"), 404
    services.score_async(current_app._get_current_object(), sub.id)
    flash("已重新送出評分。同一張圖會沿用既有判讀，分數保持一致。")
    return redirect(url_for("front.submission", sid=sid))


@bp.route("/file/<int:sid>/<which>")
@login_required()
def file(sid, which):
    sub = db.session.get(Submission, sid)
    if not sub or not can_view(current_user(), sub):
        return render_template("message.html", title="無法檢視", msg="找不到檔案。"), 404
    if which == "collab":
        rel, name = sub.collab_path, sub.collab_name
    elif which == "text":
        rel, name = sub.text.file_path, sub.text.file_name
    else:
        m = next((m for m in sub.members if str(m.id) == which), None)
        rel, name = (m.file_path, m.file_name) if m else ("", "")
    full = os.path.join(current_app.config["UPLOAD_DIR"], rel) if rel else ""
    if not rel or not os.path.exists(full):
        return render_template("message.html", title="找不到檔案", msg="這個檔案不存在。"), 404
    return send_file(full, download_name=name, as_attachment=False)
