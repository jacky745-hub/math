"""端對端測試：資料庫綁定、註冊登入、上傳、判讀匯入、計分一致性、匯出、權限。"""
import io
import json
import os
import threading

import pytest

os.environ["CM_NO_AUTOCREATE"] = "1"
os.environ.pop("ANTHROPIC_API_KEY", None)
from src.extensions import db  # noqa: E402
from src.main import create_app  # noqa: E402
from src.models import Contribution, MapScore, Submission, User  # noqa: E402

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 64


def rel(a, b, level=None, owner="", label=""):
    return {"a": a, "b": b, "label": label, "valid": True, "level": level, "owner": owner, "note": ""}


def bundle():
    ind1 = {"root": "A", "relations": [rel("A", "B", 1, label="分為"), rel("B", "C", 2), rel("A", "D", 1)],
            "examples": [{"parent": "C", "item": "c1", "valid": True, "owner": "", "note": ""}], "cross_links": []}
    ind2 = {"root": "A", "relations": [rel("A", "B", 1), {"a": "B", "b": "Z", "label": "", "valid": False, "level": 2, "owner": "", "note": "與文本不符"}],
            "examples": [], "cross_links": []}
    collab = {"root": "A", "nodes": [{"id": "A", "owner": "1", "rings": ["2"], "example": False, "valid": True},
                                     {"id": "B", "owner": "1", "rings": [], "example": False, "valid": True}],
              "relations": [rel("A", "B", 1, owner="1")], "examples": [], "cross_links": []}
    inv = {"root": "A", "concepts": [{"id": "A", "importance": "core"}, {"id": "Q", "importance": "core"}], "standard_score": 40}
    return {"inventory": inv, "collab": collab, "individual": {"1": ind1, "2": ind2}}


@pytest.fixture()
def app(tmp_path):
    app = create_app({"TESTING": True, "DATA_DIR": str(tmp_path), "SECRET_KEY": "t"})
    return app


@pytest.fixture()
def client(app):
    return app.test_client()


def login(c, u, p):
    return c.post("/login", data={"username": u, "password": p}, follow_redirects=True)


def register(c, u, role="student", **kw):
    data = {"username": u, "password": "secret1", "password2": "secret1", "role": role, "name": u, "school": "S", "class_name": "801"}
    data.update(kw)
    return c.post("/register", data=data, follow_redirects=True)


def admin_login(app, c):
    pw = open(os.path.join(app.config["DATA_DIR"], "admin_initial_password.txt"), encoding="utf-8").read().split("密碼：")[1].split()[0]
    assert "後台管理" in login(c, "admin", pw).get_data(as_text=True)


def upload(c, collab=PNG, m1=PNG + b"1", m2=PNG + b"2", text="A 分為 B 與 D。B 包含 C，例如 c1。"):
    return c.post("/upload", data={
        "school": "S", "class_name": "801", "group_name": "G", "text_title": "T", "text_content": text,
        "seat_no": ["1", "2"], "name": ["甲", "乙"], "color": ["紅", "藍"], "page": ["1", "1"],
        "member_file": [(io.BytesIO(m1), "a.png"), (io.BytesIO(m2), "b.png")],
        "collab_file": (io.BytesIO(collab), "c.png"), "collab_page": "1"},
        content_type="multipart/form-data", follow_redirects=True)


def test_db_bound_in_request_thread_and_cli(app, client):
    """重現並防止『The current Flask app is not registered with this SQLAlchemy instance』。"""
    assert "sqlalchemy" in app.extensions
    assert client.get("/healthz").json == {"ok": True}
    out = {}

    def worker():
        with app.app_context():
            out["n"] = User.query.count()
            db.session.remove()
    t = threading.Thread(target=worker)
    t.start()
    t.join()
    assert out["n"] == 1  # 預設 admin


def test_auth_flow(client):
    assert "註冊成功" in register(client, "stu1").get_data(as_text=True)
    assert client.get("/admin/").status_code == 403
    client.get("/logout")
    assert client.get("/upload").status_code == 302
    assert "帳號或密碼不正確" in login(client, "stu1", "bad").get_data(as_text=True)
    assert "我的小組" in login(client, "stu1", "secret1").get_data(as_text=True)
    client.get("/logout")
    assert "教師註冊碼不正確" in register(client, "tea1", role="teacher").get_data(as_text=True)
    assert "須由 admin" in register(client, "mgr1", role="admin").get_data(as_text=True)


def test_upload_validation_messages(client):
    register(client, "stu1")
    r = client.post("/upload", data={"school": "S", "class_name": "801", "text_content": "x", "seat_no": ["1", "2"],
                                     "name": ["a", "b"], "color": ["紅", "紅"], "page": ["1", "1"],
                                     "member_file": [(io.BytesIO(PNG), "a.png"), (io.BytesIO(PNG), "b.png")],
                                     "collab_file": (io.BytesIO(PNG), "c.png")}, content_type="multipart/form-data")
    assert "顏色必須不同" in r.get_data(as_text=True)
    assert "上傳失敗" not in r.get_data(as_text=True)


def test_full_pipeline_and_reliability(app, client):
    register(client, "stu1", seat_no="1")
    page = upload(client).get_data(as_text=True)
    assert "上傳成功" in page and "尚待判讀" in page          # 無 AI 金鑰：存檔成功、等待判讀，不報錯
    with app.app_context():
        s = Submission.query.one()
        assert s.status == "pending" and os.path.exists(os.path.join(app.config["UPLOAD_DIR"], s.collab_path))
    assert client.get("/file/1/collab").status_code == 200
    client.get("/logout")
    admin_login(app, client)
    r = client.post("/admin/submission/1/analysis", data={"bundle": json.dumps(bundle(), ensure_ascii=False)}, follow_redirects=True)
    html = r.get_data(as_text=True)
    assert "判讀已匯入並完成計分" in html and "公式一" in html
    with app.app_context():
        sc = {(x.map_type, x.member.seat_no if x.member else ""): x for x in MapScore.query.all()}
        a = sc[("individual", "1")]
        assert (a.relations_n, a.hierarchy_n, a.examples_n, a.cross_n, a.total) == (3, 2, 1, 0, 14)
        b = sc[("individual", "2")]
        assert (b.relations_n, b.hierarchy_n, b.total) == (1, 1, 6)        # 無效連結不計分、也不計階層
        assert sc[("collab", "")].total == 6
        assert "B — Z" in b.detail[0]["得分細節"] and "未計分" in b.detail[0]["得分細節"]
        con = {c.member.seat_no: c for c in Contribution.query.all()}
        c1 = con["1"]
        # 座號1：親筆 A、B 兩概念＋A—B；補登 B—C、A—D、例子 c1、概念 C、D
        assert (c1.d_concepts, c1.d_relations, c1.d_hierarchy, c1.d_examples) == (4, 3, 2, 1)
        assert c1.collab_score == 4 * 0.5 + 3 + 10 + 1
        assert con["2"].d_concepts == 0.5 and con["2"].collab_score == 0.25   # 只有圈選認同
        first = [(x.map_type, x.member_id, x.total, x.detail_json) for x in MapScore.query.order_by(MapScore.id)]
        f_first = sorted((c.member.seat_no, c.f1, c.f2, c.f3) for c in Contribution.query.all())
    # 同一組檔案再上傳一次（間隔多久都一樣）→ 直接取用同一份判讀，分數與細節完全一致
    upload(client)
    with app.app_context():
        s2 = db.session.get(Submission, 2)
        assert s2.status == "scored"
        second = [(x.map_type, x.total, x.detail_json) for x in MapScore.query.filter_by(submission_id=2).order_by(MapScore.id)]
        assert [(a, c, d) for a, _, c, d in first] == second
        assert f_first == sorted((c.member.seat_no, c.f1, c.f2, c.f3) for c in Contribution.query.filter_by(submission_id=2))
    # 圖檔內容不同 → 視為另一張圖，不會誤用舊判讀
    upload(client, m1=PNG + b"changed")
    with app.app_context():
        assert db.session.get(Submission, 3).status == "pending"
    # 匯出
    for url in ["groups", "scores", "details", "contributions", "users"]:
        r = client.get(f"/admin/export/{url}.csv")
        assert r.status_code == 200 and r.data.startswith(b"\xef\xbb\xbf")
    assert "得分細節".encode() in client.get("/admin/export/details.csv").data
    x = client.get("/admin/export/all.xlsx")
    assert x.status_code == 200 and x.data[:2] == b"PK"
    from openpyxl import load_workbook
    wb = load_workbook(io.BytesIO(x.data))
    assert wb.sheetnames == ["小組", "個人與協作圖評分", "評分細節", "貢獻值", "使用者"]
    assert client.get("/admin/export/files.zip").data[:2] == b"PK"
    assert client.get("/admin/export/analysis.json").status_code == 200
    # 重新評分按鈕
    assert "已重新送出評分" in client.post("/submission/1/rescore", follow_redirects=True).get_data(as_text=True)


def test_roles_and_removal(app, client):
    register(client, "stu1")
    client.get("/logout")
    register(client, "stu2")
    client.get("/logout")
    admin_login(app, client)
    with app.app_context():
        ids = {u.username: u.id for u in User.query.all()}
    assert "身分改為 管理者" in client.post(f"/admin/users/{ids['stu2']}/role", data={"role": "manager"}, follow_redirects=True).get_data(as_text=True)
    assert "至少要保留一位 admin" in client.post(f"/admin/users/{ids['admin']}/role", data={"role": "student"}, follow_redirects=True).get_data(as_text=True)
    client.get("/logout")
    login(client, "stu2", "secret1")                      # 管理者
    assert client.get("/admin/users").status_code == 200
    assert "只能剔除身分低於自己" in client.post(f"/admin/users/{ids['admin']}/delete", follow_redirects=True).get_data(as_text=True)
    assert client.post(f"/admin/users/{ids['stu1']}/role", data={"role": "admin"}).status_code == 403
    assert "已剔除帳號 stu1" in client.post(f"/admin/users/{ids['stu1']}/delete", follow_redirects=True).get_data(as_text=True)
    client.get("/logout")
    admin_login(app, client)
    assert "已剔除帳號 stu2" in client.post(f"/admin/users/{ids['stu2']}/delete", follow_redirects=True).get_data(as_text=True)
    r = client.post("/admin/settings", data={"w_concepts": "0.5", "w_relations": "1", "w_hierarchy": "5", "w_cross": "10",
                                             "w_examples": "1", "supplement_coef": "0.5", "ring_coef": "0.5", "standard_score": "",
                                             "teacher_code": "TEACH"}, follow_redirects=True)
    assert "設定已儲存" in r.get_data(as_text=True)
    client.get("/logout")
    assert "註冊成功" in register(client, "tea1", role="teacher", teacher_code="TEACH").get_data(as_text=True)
    assert client.get("/admin/").status_code == 200 and client.get("/admin/users").status_code == 403
