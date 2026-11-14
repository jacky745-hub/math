"""上傳檔案儲存、判讀快取、評分流程。"""
import hashlib
import json
import os
import threading
import uuid

from flask import current_app

from src import ai_engine, scoring
from src.extensions import db
from src.models import (AnalysisCache, Contribution, MapScore, Submission, get_settings, now)

ALLOWED = {"pdf", "png", "jpg", "jpeg", "gif", "webp", "bmp", "tif", "tiff", "heic", "doc", "docx", "ppt", "pptx", "txt", "svg"}


def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()


def save_upload(fs, sub="maps"):
    """儲存上傳檔，回傳 (相對路徑, 原檔名, sha256)。檔名以雜湊命名，同一檔案只存一份。"""
    data = fs.read()
    if not data:
        raise ValueError("檔案是空的，請重新選擇檔案。")
    orig = fs.filename or "upload"
    ext = orig.rsplit(".", 1)[-1].lower() if "." in orig else ""
    if ext not in ALLOWED:
        raise ValueError(f"不支援的檔案格式「.{ext}」。可上傳：PDF、圖片（PNG/JPG/GIF/WEBP/BMP/TIFF/HEIC）、Word、PowerPoint、TXT。")
    digest = sha256_bytes(data)
    folder = os.path.join(current_app.config["UPLOAD_DIR"], sub)
    os.makedirs(folder, exist_ok=True)
    rel = os.path.join(sub, f"{digest}.{ext}")
    full = os.path.join(current_app.config["UPLOAD_DIR"], rel)
    if not os.path.exists(full):
        tmp = full + "." + uuid.uuid4().hex
        with open(tmp, "wb") as f:
            f.write(data)
        os.replace(tmp, full)
    name = os.path.basename(orig.replace("\\", "/")).replace("\x00", "")[:150] or "upload"  # 保留中文檔名
    return rel, name, digest


def _key(*parts):
    return hashlib.sha256("|".join(str(p) for p in parts).encode()).hexdigest()


def inventory_key(text):
    return _key("inventory", scoring.RUBRIC_VERSION, text.sha256)


def map_key(sub, member=None):
    members_sig = ",".join(f"{m.seat_no}:{m.color}" for m in sub.members)
    if member is None:
        return _key("collab", scoring.RUBRIC_VERSION, sub.text.sha256, sub.collab_sha, sub.collab_page, members_sig)
    return _key("individual", scoring.RUBRIC_VERSION, sub.text.sha256, member.file_sha, member.page, member.seat_no)


def cache_get(key):
    row = db.session.get(AnalysisCache, key)
    return row.data if row else None


def cache_put(key, kind, data, engine, overwrite=False):
    row = db.session.get(AnalysisCache, key)
    if row and not overwrite:
        return row.data
    if not row:
        row = AnalysisCache(key=key, kind=kind)
        db.session.add(row)
    row.engine, row.data_json, row.created_at = engine, json.dumps(data, ensure_ascii=False, sort_keys=True), now()
    db.session.commit()
    return data


def _full(rel):
    return os.path.join(current_app.config["UPLOAD_DIR"], rel) if rel else ""


def gather_analyses(sub, use_ai=True):
    """取回（或產生）文本清單與每張圖的判讀。回傳 (inventory, collab, {seat: analysis}, 缺少清單, 引擎名稱)。"""
    missing, engines = [], set()
    ai_ok = use_ai and ai_engine.available()

    def obtain(key, kind, label, producer):
        row = db.session.get(AnalysisCache, key)
        if row:
            engines.add(row.engine)
            return row.data
        if ai_ok:
            data = producer()
            cache_put(key, kind, data, f"AI:{ai_engine.MODEL}")
            engines.add(f"AI:{ai_engine.MODEL}")
            return data
        missing.append(label)
        return None

    text = sub.text
    inv = obtain(inventory_key(text), "inventory", "文本概念清單",
                 lambda: ai_engine.build_inventory(text.content, _full(text.file_path), text.file_name))
    members = [{"seat": m.seat_no, "color": m.color} for m in sub.members]
    inds = {}
    for m in sub.members:
        inds[m.seat_no] = obtain(map_key(sub, m), "individual", f"座號 {m.seat_no} 個人圖",
                                 lambda m=m: ai_engine.analyze_map(text.content, inv or {}, _full(m.file_path), m.file_name,
                                                                   m.page, "individual", seat=m.seat_no))
    collab = obtain(map_key(sub), "collab", "協作圖",
                    lambda: ai_engine.analyze_map(text.content, inv or {}, _full(sub.collab_path), sub.collab_name,
                                                  sub.collab_page, "collab", members=members))
    return inv, collab, inds, missing, "、".join(sorted(engines))


def score_submission(sub_id, use_ai=True):
    """評分主流程。任何例外都會被接住並寫入 status_msg，不會讓使用者看到「上傳失敗」。"""
    sub = db.session.get(Submission, sub_id)
    if not sub:
        return
    try:
        sub.status, sub.status_msg = "scoring", "判讀與評分進行中…"
        db.session.commit()
        inv, collab, inds, missing, engine = gather_analyses(sub, use_ai)
        if missing:
            sub.status = "pending"
            sub.status_msg = ("檔案已安全存檔。尚待判讀：" + "、".join(missing) +
                              "。（系統未設定 AI 金鑰時，請教師於後台「判讀匯入」完成判讀，分數即會自動產生。）")
            db.session.commit()
            return
        settings = get_settings()
        std = float(settings["standard_score"]) if settings.get("standard_score") else (inv.get("standard_score") or None)
        MapScore.query.filter_by(submission_id=sub.id).delete()
        Contribution.query.filter_by(submission_id=sub.id).delete()
        res, summary = scoring.contribution(collab, inds, settings, std)

        def store(analysis, member, map_type, key):
            sc = scoring.novak_score(analysis)
            fb = ""
            if member is not None:
                fb, _ = scoring.individual_feedback(member.name, analysis, sc, inv, summary["standard"])
            c, p = sc["counts"], sc["pts"]
            db.session.add(MapScore(
                submission_id=sub.id, member_id=member.id if member else None, map_type=map_type,
                relations_n=c["relations"], relations_pts=p["relations"], hierarchy_n=c["hierarchy"],
                hierarchy_pts=p["hierarchy"], examples_n=c["examples"], examples_pts=p["examples"],
                cross_n=c["cross"], cross_pts=p["cross"], total=sc["total"],
                detail_json=json.dumps(sc["rows"], ensure_ascii=False), feedback=fb, analysis_key=key))

        store(collab, None, "collab", map_key(sub))
        for m in sub.members:
            store(inds[m.seat_no], m, "individual", map_key(sub, m))
            r = res[m.seat_no]
            f1, f2, f3, g = scoring.contribution_feedback(m.name, r, summary)
            D = r["D"]
            db.session.add(Contribution(
                submission_id=sub.id, member_id=m.id, d_concepts=D["concepts"], d_relations=D["relations"],
                d_hierarchy=D["hierarchy"], d_cross=D["cross"], d_examples=D["examples"],
                individual_score=r["P"], collab_score=r["C"], bonus=r["bonus"], f1=r["f1"], f2=r["f2"], f3=r["f3"],
                role_type=r["role"], path=r["path"], detail_json=json.dumps(r, ensure_ascii=False),
                feedback_f1=f1, feedback_f2=f2, feedback_f3=f3, feedback_guidance=g))
        sub.summary_json = json.dumps(summary, ensure_ascii=False)
        sub.status, sub.status_msg, sub.engine, sub.scored_at = "scored", "評分完成", engine, now()
        db.session.commit()
    except Exception as e:  # noqa: BLE001
        db.session.rollback()
        sub = db.session.get(Submission, sub_id)
        sub.status = "error"
        sub.status_msg = f"檔案已安全存檔，但判讀時發生問題：{e}。請按「重新評分」，或由教師於後台匯入判讀。"
        db.session.commit()


def score_async(app, sub_id):
    """背景執行評分。傳入『真正的 app 物件』並在其 app_context 內使用同一個 db 實例。"""
    def run():
        with app.app_context():
            try:
                score_submission(sub_id)
            finally:
                db.session.remove()
    if app.config.get("TESTING") or app.config.get("SCORE_SYNC"):
        score_submission(sub_id)
    else:
        threading.Thread(target=run, daemon=True).start()
