from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Literal


class FileKind(str, Enum):
    IMAGE = "image"
    PDF = "pdf"
    UNKNOWN = "unknown"


class HintLevel(int, Enum):
    L0 = 0  # no hint, just a reflection prompt
    L1 = 1  # gentle nudge (direction)
    L2 = 2  # strategic hint (method)
    L3 = 3  # worked micro-step (one step)
    L4 = 4  # near-solution (still asks student to do last step)


class ErrorTag(str, Enum):
    # Core junior-high frequent misconception buckets
    SIGN_ERROR = "sign_error"
    DISTRIBUTION_ERROR = "distribution_error"
    FRACTION_OPERATION = "fraction_operation"
    LIKE_TERMS = "like_terms"
    EQUATION_BALANCE = "equation_balance"
    TRANSPOSE_ERROR = "transpose_error"
    ARITHMETIC_CARELESS = "arithmetic_careless"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class SubmissionInput:
    student_id: str
    grade: str | None
    assignment_id: str | None
    problem_text: str
    work_text: str | None
    final_answer_text: str | None
    upload_path: str | None
    upload_kind: FileKind
    extracted_text: str | None


@dataclass(frozen=True)
class DetectedIssue:
    tag: ErrorTag
    evidence: str
    misconception: str


@dataclass(frozen=True)
class ScaffoldTurn:
    level: HintLevel
    title: str
    message: str
    metacognition_prompt: str


@dataclass(frozen=True)
class AnalysisResult:
    is_correct: bool | None
    short_feedback: str
    issues: list[DetectedIssue]
    hint_path: list[ScaffoldTurn]
    debug: dict[str, Any]
    first_wrong_step_index: int | None = None
    first_wrong_step_text: str | None = None


ExportFormat = Literal["errors_csv", "submissions_csv"]

