import json
from datetime import datetime, timezone

from werkzeug.security import check_password_hash, generate_password_hash

from src.extensions import db

ROLES = ["student", "teacher", "manager", "admin"]
ROLE_LABEL = {"student": "學生", "teacher": "教師", "manager": "管理者", "admin": "admin（最高管理者）"}
ROLE_RANK = {r: i for i, r in enumerate(ROLES)}


def now():
    return datetime.now(timezone.utc)


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    name = db.Column(db.String(80), default="")
    role = db.Column(db.String(20), default="student", nullable=False)
    school = db.Column(db.String(120), default="")
    class_name = db.Column(db.String(40), default="")
    seat_no = db.Column(db.String(10), default="")
    created_at = db.Column(db.DateTime, default=now)

    def set_password(self, pw):
        self.password_hash = generate_password_hash(pw)

    def check_password(self, pw):
        return check_password_hash(self.password_hash, pw)

    @property
    def rank(self):
        return ROLE_RANK.get(self.role, 0)

    @property
    def role_label(self):
        return ROLE_LABEL.get(self.role, self.role)


class TextDoc(db.Model):
    """概念圖文本（學生依此文本繪製概念圖，也是評分依據）。"""
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), default="")
    content = db.Column(db.Text, default="")
    file_path = db.Column(db.String(300), default="")
    file_name = db.Column(db.String(200), default="")
    sha256 = db.Column(db.String(64), index=True)
    created_by = db.Column(db.Integer, db.ForeignKey("user.id"))
    created_at = db.Column(db.DateTime, default=now)


class Submission(db.Model):
    """一個小組的一次上傳（文本＋每人個人圖＋協作圖）。"""
    id = db.Column(db.Integer, primary_key=True)
    school = db.Column(db.String(120), default="")
    class_name = db.Column(db.String(40), default="")
    group_name = db.Column(db.String(80), default="")
    text_id = db.Column(db.Integer, db.ForeignKey("text_doc.id"))
    collab_path = db.Column(db.String(300), default="")
    collab_name = db.Column(db.String(200), default="")
    collab_sha = db.Column(db.String(64), default="")
    collab_page = db.Column(db.Integer, default=1)
    status = db.Column(db.String(20), default="pending")  # pending / scoring / scored / error
    status_msg = db.Column(db.Text, default="")
    engine = db.Column(db.String(60), default="")
    summary_json = db.Column(db.Text, default="{}")
    created_by = db.Column(db.Integer, db.ForeignKey("user.id"))
    created_at = db.Column(db.DateTime, default=now)
    scored_at = db.Column(db.DateTime)

    text = db.relationship("TextDoc")
    creator = db.relationship("User")
    members = db.relationship("Member", backref="submission", cascade="all, delete-orphan",
                              order_by="Member.order")
    scores = db.relationship("MapScore", backref="submission", cascade="all, delete-orphan")
    contributions = db.relationship("Contribution", backref="submission", cascade="all, delete-orphan")

    @property
    def summary(self):
        return json.loads(self.summary_json or "{}")


class Member(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    submission_id = db.Column(db.Integer, db.ForeignKey("submission.id"), nullable=False)
    order = db.Column(db.Integer, default=0)
    seat_no = db.Column(db.String(10), default="")
    name = db.Column(db.String(80), default="")
    color = db.Column(db.String(40), default="")
    file_path = db.Column(db.String(300), default="")
    file_name = db.Column(db.String(200), default="")
    file_sha = db.Column(db.String(64), default="")
    page = db.Column(db.Integer, default=1)


class MapScore(db.Model):
    """一張概念圖（個人圖或協作圖）的 Novak 評分。"""
    id = db.Column(db.Integer, primary_key=True)
    submission_id = db.Column(db.Integer, db.ForeignKey("submission.id"), nullable=False)
    member_id = db.Column(db.Integer, db.ForeignKey("member.id"))  # None = 協作圖
    map_type = db.Column(db.String(20))  # individual / collab
    relations_n = db.Column(db.Integer, default=0)
    relations_pts = db.Column(db.Float, default=0)
    hierarchy_n = db.Column(db.Integer, default=0)
    hierarchy_pts = db.Column(db.Float, default=0)
    examples_n = db.Column(db.Integer, default=0)
    examples_pts = db.Column(db.Float, default=0)
    cross_n = db.Column(db.Integer, default=0)
    cross_pts = db.Column(db.Float, default=0)
    total = db.Column(db.Float, default=0)
    detail_json = db.Column(db.Text, default="[]")   # [{項目, 得分細節, 得分, 說明}]
    feedback = db.Column(db.Text, default="")
    analysis_key = db.Column(db.String(64), default="")
    member = db.relationship("Member")

    @property
    def detail(self):
        return json.loads(self.detail_json or "[]")


class Contribution(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    submission_id = db.Column(db.Integer, db.ForeignKey("submission.id"), nullable=False)
    member_id = db.Column(db.Integer, db.ForeignKey("member.id"), nullable=False)
    d_concepts = db.Column(db.Float, default=0)
    d_relations = db.Column(db.Float, default=0)
    d_hierarchy = db.Column(db.Float, default=0)
    d_cross = db.Column(db.Float, default=0)
    d_examples = db.Column(db.Float, default=0)
    individual_score = db.Column(db.Float, default=0)
    collab_score = db.Column(db.Float, default=0)      # 協作概念圖個人貢獻分數
    bonus = db.Column(db.Float, default=0)             # 協作效益加成
    f1 = db.Column(db.Float, default=0)
    f2 = db.Column(db.Float, default=0)
    f3 = db.Column(db.Float, default=0)
    role_type = db.Column(db.String(20), default="")
    path = db.Column(db.String(60), default="")
    detail_json = db.Column(db.Text, default="{}")
    feedback_f1 = db.Column(db.Text, default="")
    feedback_f2 = db.Column(db.Text, default="")
    feedback_f3 = db.Column(db.Text, default="")
    feedback_guidance = db.Column(db.Text, default="")
    member = db.relationship("Member")

    @property
    def detail(self):
        return json.loads(self.detail_json or "{}")


class AnalysisCache(db.Model):
    """判讀結果快取：同一份文本＋同一張圖（內容雜湊相同）永遠取回同一份判讀，
    因此不論間隔多久重傳，評分細節與分數完全一致（鎖定信度）。"""
    key = db.Column(db.String(64), primary_key=True)
    kind = db.Column(db.String(20))  # inventory / individual / collab
    engine = db.Column(db.String(60), default="")
    data_json = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=now)

    @property
    def data(self):
        return json.loads(self.data_json)


class Setting(db.Model):
    key = db.Column(db.String(60), primary_key=True)
    value = db.Column(db.Text, default="")


DEFAULT_SETTINGS = {
    "w_concepts": "0.5", "w_relations": "1", "w_hierarchy": "5", "w_cross": "10", "w_examples": "1",
    "supplement_coef": "1.0", "ring_coef": "0.5",
    "standard_score": "",          # 留空＝使用文本標準參考圖分數
    "teacher_code": "",            # 教師註冊碼（留空＝教師帳號需由管理者升級）
}


def get_settings():
    s = dict(DEFAULT_SETTINGS)
    for row in Setting.query.all():
        s[row.key] = row.value
    return s
