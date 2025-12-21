from __future__ import annotations

import csv
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path

from .models import AnalysisResult, HintLevel, SubmissionInput


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def ensure_data_dirs(base_dir: Path) -> dict[str, Path]:
    base_dir.mkdir(parents=True, exist_ok=True)
    uploads = base_dir / "uploads"
    uploads.mkdir(parents=True, exist_ok=True)
    return {"base": base_dir, "uploads": uploads, "db": base_dir / "mathcoach.sqlite3"}


@contextmanager
def connect(db_path: Path):
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(db_path))
    try:
        con.row_factory = sqlite3.Row
        yield con
        con.commit()
    finally:
        con.close()


def init_db(db_path: Path) -> None:
    with connect(db_path) as con:
        con.executescript(
            """
            PRAGMA journal_mode=WAL;

            CREATE TABLE IF NOT EXISTS submissions (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              created_at TEXT NOT NULL,
              student_id TEXT NOT NULL,
              grade TEXT,
              assignment_id TEXT,
              problem_text TEXT NOT NULL,
              work_text TEXT,
              final_answer_text TEXT,
              upload_path TEXT,
              upload_kind TEXT NOT NULL,
              extracted_text TEXT,
              is_correct INTEGER,
              short_feedback TEXT,
              first_wrong_step_index INTEGER,
              first_wrong_step_text TEXT
            );

            CREATE TABLE IF NOT EXISTS issues (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              submission_id INTEGER NOT NULL,
              tag TEXT NOT NULL,
              evidence TEXT NOT NULL,
              misconception TEXT NOT NULL,
              FOREIGN KEY (submission_id) REFERENCES submissions(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS hint_events (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              submission_id INTEGER NOT NULL,
              shown_at TEXT NOT NULL,
              level INTEGER NOT NULL,
              FOREIGN KEY (submission_id) REFERENCES submissions(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS reflections (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              submission_id INTEGER NOT NULL,
              created_at TEXT NOT NULL,
              reflection_text TEXT NOT NULL,
              FOREIGN KEY (submission_id) REFERENCES submissions(id) ON DELETE CASCADE
            );
            """
        )

        # Lightweight migration for existing DBs (if table existed before)
        _ensure_column(con, "submissions", "first_wrong_step_index", "INTEGER")
        _ensure_column(con, "submissions", "first_wrong_step_text", "TEXT")


def _ensure_column(con: sqlite3.Connection, table: str, column: str, col_type: str) -> None:
    cols = [r["name"] for r in con.execute(f"PRAGMA table_info({table})").fetchall()]
    if column in cols:
        return
    con.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")


def insert_submission(db_path: Path, sub: SubmissionInput) -> int:
    init_db(db_path)
    with connect(db_path) as con:
        cur = con.execute(
            """
            INSERT INTO submissions (
              created_at, student_id, grade, assignment_id,
              problem_text, work_text, final_answer_text,
              upload_path, upload_kind, extracted_text,
              is_correct, short_feedback
            ) VALUES (
              :created_at, :student_id, :grade, :assignment_id,
              :problem_text, :work_text, :final_answer_text,
              :upload_path, :upload_kind, :extracted_text,
              NULL, NULL
            )
            """,
            {
                "created_at": utc_now_iso(),
                "student_id": sub.student_id.strip(),
                "grade": sub.grade,
                "assignment_id": sub.assignment_id,
                "problem_text": sub.problem_text,
                "work_text": sub.work_text,
                "final_answer_text": sub.final_answer_text,
                "upload_path": sub.upload_path,
                "upload_kind": sub.upload_kind.value,
                "extracted_text": sub.extracted_text,
            },
        )
        return int(cur.lastrowid)


def save_analysis(db_path: Path, submission_id: int, result: AnalysisResult) -> None:
    init_db(db_path)
    with connect(db_path) as con:
        is_correct_int = None
        if result.is_correct is True:
            is_correct_int = 1
        elif result.is_correct is False:
            is_correct_int = 0

        con.execute(
            """
            UPDATE submissions
            SET is_correct = :is_correct,
                short_feedback = :short_feedback,
                first_wrong_step_index = :first_wrong_step_index,
                first_wrong_step_text = :first_wrong_step_text
            WHERE id = :id
            """,
            {
                "id": submission_id,
                "is_correct": is_correct_int,
                "short_feedback": result.short_feedback,
                "first_wrong_step_index": result.first_wrong_step_index,
                "first_wrong_step_text": result.first_wrong_step_text,
            },
        )

        con.execute("DELETE FROM issues WHERE submission_id = ?", (submission_id,))
        con.executemany(
            """
            INSERT INTO issues (submission_id, tag, evidence, misconception)
            VALUES (?, ?, ?, ?)
            """,
            [
                (submission_id, issue.tag.value, issue.evidence, issue.misconception)
                for issue in result.issues
            ],
        )


def record_hint_shown(db_path: Path, submission_id: int, level: HintLevel) -> None:
    init_db(db_path)
    with connect(db_path) as con:
        con.execute(
            """
            INSERT INTO hint_events (submission_id, shown_at, level)
            VALUES (?, ?, ?)
            """,
            (submission_id, utc_now_iso(), int(level.value)),
        )


def save_reflection(db_path: Path, submission_id: int, reflection_text: str) -> None:
    init_db(db_path)
    text = (reflection_text or "").strip()
    if not text:
        return
    with connect(db_path) as con:
        con.execute(
            """
            INSERT INTO reflections (submission_id, created_at, reflection_text)
            VALUES (?, ?, ?)
            """,
            (submission_id, utc_now_iso(), text),
        )


def get_recent_submissions(db_path: Path, limit: int = 100) -> list[sqlite3.Row]:
    init_db(db_path)
    with connect(db_path) as con:
        cur = con.execute(
            """
            SELECT *
            FROM submissions
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        )
        return list(cur.fetchall())


def export_errors_csv(db_path: Path) -> str:
    """
    Row-per-issue export, joined with submission metadata and hint usage counts.
    Returns CSV text (UTF-8).
    """
    init_db(db_path)
    with connect(db_path) as con:
        rows = con.execute(
            """
            WITH hint_counts AS (
              SELECT submission_id, MAX(level) AS max_hint_level, COUNT(*) AS hint_events
              FROM hint_events
              GROUP BY submission_id
            )
            SELECT
              s.id AS submission_id,
              s.created_at,
              s.student_id,
              s.grade,
              s.assignment_id,
              s.problem_text,
              s.final_answer_text,
              s.is_correct,
              s.first_wrong_step_index,
              s.first_wrong_step_text,
              COALESCE(h.max_hint_level, 0) AS max_hint_level,
              COALESCE(h.hint_events, 0) AS hint_events,
              i.tag,
              i.evidence,
              i.misconception
            FROM issues i
            JOIN submissions s ON s.id = i.submission_id
            LEFT JOIN hint_counts h ON h.submission_id = s.id
            ORDER BY s.id DESC, i.id ASC
            """
        ).fetchall()

    buf = StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        [
            "submission_id",
            "created_at",
            "student_id",
            "grade",
            "assignment_id",
            "problem_text",
            "final_answer_text",
            "is_correct",
            "first_wrong_step_index",
            "first_wrong_step_text",
            "max_hint_level",
            "hint_events",
            "tag",
            "evidence",
            "misconception",
        ]
    )
    for r in rows:
        writer.writerow(
            [
                r["submission_id"],
                r["created_at"],
                r["student_id"],
                r["grade"],
                r["assignment_id"],
                r["problem_text"],
                r["final_answer_text"],
                r["is_correct"],
                r["first_wrong_step_index"],
                r["first_wrong_step_text"],
                r["max_hint_level"],
                r["hint_events"],
                r["tag"],
                r["evidence"],
                r["misconception"],
            ]
        )
    return buf.getvalue()


def export_submissions_csv(db_path: Path) -> str:
    init_db(db_path)
    with connect(db_path) as con:
        rows = con.execute(
            """
            SELECT
              id,
              created_at,
              student_id,
              grade,
              assignment_id,
              is_correct,
              short_feedback,
              first_wrong_step_index,
              first_wrong_step_text,
              upload_kind,
              upload_path
            FROM submissions
            ORDER BY id DESC
            """
        ).fetchall()

    buf = StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        [
            "submission_id",
            "created_at",
            "student_id",
            "grade",
            "assignment_id",
            "is_correct",
            "short_feedback",
            "first_wrong_step_index",
            "first_wrong_step_text",
            "upload_kind",
            "upload_path",
        ]
    )
    for r in rows:
        writer.writerow(
            [
                r["id"],
                r["created_at"],
                r["student_id"],
                r["grade"],
                r["assignment_id"],
                r["is_correct"],
                r["short_feedback"],
                r["first_wrong_step_index"],
                r["first_wrong_step_text"],
                r["upload_kind"],
                r["upload_path"],
            ]
        )
    return buf.getvalue()

