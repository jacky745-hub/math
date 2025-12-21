from __future__ import annotations

import os
import uuid
from pathlib import Path

import pandas as pd
import streamlit as st

from mathcoach import analyzer, db, extract
from mathcoach.models import FileKind, HintLevel, SubmissionInput


APP_TITLE = "國中數學｜逐步鷹架解題與錯因回饋（MVP）"
DATA_DIR = Path(os.environ.get("MATHCOACH_DATA_DIR", "data"))
DIRS = db.ensure_data_dirs(DATA_DIR)
DB_PATH = DIRS["db"]
UPLOAD_DIR = DIRS["uploads"]


def _save_upload(upload) -> tuple[str | None, FileKind]:
    if upload is None:
        return None, FileKind.UNKNOWN
    kind = extract.detect_file_kind(upload.name)
    uid = uuid.uuid4().hex[:12]
    safe_name = "".join(ch for ch in upload.name if ch.isalnum() or ch in ("-", "_", ".", " "))
    out = UPLOAD_DIR / f"{uid}_{safe_name}"
    out.write_bytes(upload.getbuffer())
    return str(out), kind


def _require_admin() -> bool:
    expected = os.environ.get("MATHCOACH_ADMIN_PASSWORD", "").strip()
    if not expected:
        st.info("目前未設定管理密碼（MVP）。若要啟用，請設定環境變數 `MATHCOACH_ADMIN_PASSWORD`。")
        return True
    pw = st.text_input("管理密碼", type="password")
    return pw == expected


def student_page():
    st.subheader("學生上傳與逐步提示")
    st.caption("建議：題目文字請盡量貼上（降低 OCR 雜訊）。你也可以上傳圖片/PDF，我會嘗試用 OCR 把步驟抓出來。")

    with st.form("submit_form"):
        col1, col2, col3 = st.columns(3)
        with col1:
            student_id = st.text_input("學生代號（可匿名）", value="S001")
        with col2:
            grade = st.selectbox("年級", options=["", "七年級", "八年級", "九年級"], index=0)
        with col3:
            assignment_id = st.text_input("作業/題組代號（可選）", value="")

        problem_text = st.text_area("題目（必填）", height=120, placeholder="例：解方程式 2x+3=7")
        work_text = st.text_area(
            "你的解題過程（可貼文字/逐行；可選）",
            height=140,
            placeholder="例：2x+3=7\n2x=7-3\nx=2",
        )
        final_answer_text = st.text_input("你的最後答案（可選）", value="", placeholder="例：x=2")

        upload = st.file_uploader("上傳圖片或 PDF（可選：單題或整份作業）", type=["png", "jpg", "jpeg", "webp", "pdf"])
        use_ocr_as_work = st.checkbox("若有 OCR 文字，優先用它當作『解題過程』", value=False)

        submitted = st.form_submit_button("送出並請系統分析")

    if not submitted:
        return

    if not student_id.strip():
        st.error("請填寫學生代號。")
        return
    if not problem_text.strip():
        st.error("請至少貼上題目文字（必填）。")
        return

    upload_path, upload_kind = _save_upload(upload)
    extracted_text = extract.maybe_extract_upload_text(Path(upload_path) if upload_path else None, upload_kind)
    effective_work_text = (extracted_text if (use_ocr_as_work and extracted_text) else (work_text.strip() or None))

    sub = SubmissionInput(
        student_id=student_id.strip(),
        grade=grade or None,
        assignment_id=assignment_id.strip() or None,
        problem_text=problem_text.strip(),
        work_text=effective_work_text,
        final_answer_text=final_answer_text.strip() or None,
        upload_path=upload_path,
        upload_kind=upload_kind,
        extracted_text=extracted_text,
    )

    submission_id = db.insert_submission(DB_PATH, sub)
    result = analyzer.analyze(sub)
    db.save_analysis(DB_PATH, submission_id, result)

    st.session_state["active_submission_id"] = submission_id
    st.session_state["analysis"] = result
    st.session_state["hint_level"] = 0

    st.success(f"已收到！提交編號：{submission_id}")
    st.write(result.short_feedback)

    if extracted_text:
        with st.expander("OCR/擷取到的文字（可用來檢查 OCR 有沒有抓錯）", expanded=False):
            st.text(extracted_text)

    if result.first_wrong_step_index is not None and result.first_wrong_step_text:
        st.warning(f"我定位到第一個可能出錯的步驟：第 {result.first_wrong_step_index + 1} 行：{result.first_wrong_step_text}")

    if result.issues:
        with st.expander("我觀察到的可能錯因（先給你 1–2 個最關鍵的）", expanded=False):
            for issue in result.issues:
                st.markdown(f"- **{issue.misconception}**\n  - 觀察：{issue.evidence}")

    step_info = (result.debug or {}).get("step_check") if hasattr(result, "debug") else None
    if step_info and step_info.get("steps"):
        with st.expander("逐行等價檢查（幫你找到『從哪一步開始偏掉』）", expanded=False):
            for s in step_info["steps"]:
                ok = s.get("is_equivalent_to_previous")
                prefix = "✅" if ok is True else ("⚠️" if ok is False else "•")
                st.write(f"{prefix} 第 {int(s['index']) + 1} 行：{s['line']}  — {s['note']}")

    st.divider()
    st.subheader("逐步提示（你決定要到哪一層）")

    _render_hints_and_reflection()


def _render_hints_and_reflection():
    submission_id = st.session_state.get("active_submission_id")
    result = st.session_state.get("analysis")
    if not submission_id or not result:
        return

    hint_level = int(st.session_state.get("hint_level", 0))
    max_level = max(int(t.level.value) for t in result.hint_path) if result.hint_path else 0

    for turn in result.hint_path:
        if int(turn.level.value) <= hint_level:
            st.markdown(f"**L{int(turn.level.value)}｜{turn.title}**")
            st.write(turn.message)
            st.caption(f"後設認知提問：{turn.metacognition_prompt}")
            st.write("")

    col_a, col_b = st.columns([1, 1])
    with col_a:
        if hint_level < max_level and st.button("再給我一個提示"):
            st.session_state["hint_level"] = hint_level + 1
            db.record_hint_shown(DB_PATH, int(submission_id), HintLevel(hint_level + 1))
            st.rerun()

    with col_b:
        if hint_level > 0 and st.button("我想先收回提示（回到較少提示）"):
            st.session_state["hint_level"] = max(0, hint_level - 1)
            st.rerun()

    st.divider()
    st.subheader("寫下你的反思（會進入老師後台資料）")
    reflection = st.text_area(
        "一句話也可以：你覺得錯在哪？下次你要怎麼避免？",
        height=100,
        key="reflection_text",
        placeholder="例：我把移項當搬家，忘了符號要改。下次我用『兩邊同減 3』來想。",
    )
    if st.button("送出反思"):
        db.save_reflection(DB_PATH, int(submission_id), reflection)
        st.success("已保存反思，謝謝你！")

    with st.expander("（選用）顯示系統解析 debug 資訊", expanded=False):
        st.json(result.debug)


def admin_page():
    st.subheader("教師後台（下載錯誤/迷思概念資料）")
    if not _require_admin():
        st.warning("密碼不正確。")
        return

    rows = db.get_recent_submissions(DB_PATH, limit=200)
    if not rows:
        st.info("目前還沒有提交資料。")
        return

    df = pd.DataFrame([dict(r) for r in rows])
    st.dataframe(
        df[
            [
                "id",
                "created_at",
                "student_id",
                "grade",
                "assignment_id",
                "is_correct",
                "short_feedback",
                "upload_kind",
            ]
        ],
        use_container_width=True,
        hide_index=True,
    )

    col1, col2 = st.columns(2)
    with col1:
        csv_text = db.export_errors_csv(DB_PATH)
        st.download_button(
            "下載：錯誤/迷思概念（errors.csv）",
            data=csv_text.encode("utf-8"),
            file_name="errors.csv",
            mime="text/csv",
        )
    with col2:
        csv_text = db.export_submissions_csv(DB_PATH)
        st.download_button(
            "下載：提交清單（submissions.csv）",
            data=csv_text.encode("utf-8"),
            file_name="submissions.csv",
            mime="text/csv",
        )


def main():
    st.set_page_config(page_title=APP_TITLE, layout="wide")
    st.title(APP_TITLE)

    db.init_db(DB_PATH)

    page = st.sidebar.radio("功能", ["學生", "教師後台"], index=0)
    if page == "學生":
        student_page()
    else:
        admin_page()


if __name__ == "__main__":
    main()

