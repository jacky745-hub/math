"""Novak 概念圖計分、個人貢獻值、差異化回饋（純函式、完全決定性）。

輸入是「判讀結果」(analysis JSON)：由 AI 或教師依『上傳文本』逐項判讀學生圖上
『實際畫出』的節點／連線而得。本模組只做計算與文字組裝，不含任何特定文本的內容，
因此得分細節只會出現該張圖與該份文本的資料。

計分標準（Novak & Gowin, 1984；ITE Chp10 p.24-26）：
  關係(連結) 每個有效 1 分；階層 每個有效 5 分；交叉連結 每個有效 10 分；例子 每個 1 分。
"""
from statistics import mean, median

PTS = {"relations": 1, "hierarchy": 5, "cross": 10, "examples": 1}
RUBRIC_VERSION = "novak-1.0"


# ---------------------------------------------------------------- helpers
def _valid(items):
    return [x for x in (items or []) if x.get("valid", True)]


def rel_key(r):
    if r.get("key"):  # 判讀者可指定同義連結共用同一個 key（例如合併寫與分開寫的同一命題）
        return "R:" + str(r["key"]).strip()
    return "R:" + "|".join(sorted([str(r.get("a", "")).strip(), str(r.get("b", "")).strip()]))


def ex_key(e):
    return "E:" + str(e.get("parent", "")).strip() + ">" + str(e.get("item", "")).strip()


def cross_key(c):
    return "X:" + "|".join(sorted([str(c.get("a", "")).strip(), str(c.get("b", "")).strip()])) \
        + ">" + str(c.get("via", "")).strip()


def hierarchy_levels(relations):
    """有效階層數＝由主概念往外(下)，連續存在有效從屬連結的層數。
    每條連結的 level 由判讀者標示（子概念所在層；非從屬關係為 None）。
    放射狀概念圖同樣以『由中心往外第幾圈』為 level。"""
    levels = {int(r["level"]) for r in _valid(relations) if r.get("level") not in (None, "", 0)}
    n = 0
    while (n + 1) in levels:
        n += 1
    return n


def _fmt_rel(r):
    lab = (r.get("label") or "").strip()
    mid = f" —{lab}→ " if lab else " — "
    return f"{r.get('a')}{mid}{r.get('b')}"


def _num(lst):
    return "；".join(f"({i}) {t}" for i, t in enumerate(lst, 1)) if lst else "（無）"


# ---------------------------------------------------------------- Novak 計分
def novak_score(analysis):
    a = analysis or {}
    rels = _valid(a.get("relations"))
    exs = _valid(a.get("examples"))
    crs = _valid(a.get("cross_links"))
    lv = hierarchy_levels(a.get("relations"))
    counts = {"relations": len(rels), "hierarchy": lv, "examples": len(exs), "cross": len(crs)}
    pts = {k: counts[k] * PTS[k] for k in counts}
    total = sum(pts.values())

    invalid_rel = [x for x in (a.get("relations") or []) if not x.get("valid", True)]
    invalid_ex = [x for x in (a.get("examples") or []) if not x.get("valid", True)]
    invalid_cr = [x for x in (a.get("cross_links") or []) if not x.get("valid", True)]
    rejected = a.get("rejected") or []
    comments = a.get("comments") or {}
    unlabeled = [r for r in rels if not (r.get("label") or "").strip()]
    hier = a.get("hierarchy") or {}

    def notes(items):
        return [f"「{_fmt_rel(x) if 'a' in x else x.get('item')}」：{x['note']}" for x in items if x.get("note")]

    # --- 關係
    d_rel = "有效連結：" + _num([_fmt_rel(r) for r in rels])
    not_counted = [f"{_fmt_rel(x)}（{x.get('note') or '與文本不符或關係不成立'}）" for x in invalid_rel] + \
                  [f"{x.get('desc')}（{x.get('reason')}）" for x in rejected if x.get("category", "relations") == "relations"]
    if not_counted:
        d_rel += "\n未計分：" + _num(not_counted)
    e_rel = [comments.get("relations", "")]
    if unlabeled:
        e_rel.append(f"有 {len(unlabeled)} 條有效連線沒有寫連接詞（例如「{_fmt_rel(unlabeled[0])}」），"
                     "因兩端概念的關係與文本相符仍給分，但請補上連接詞，讓每條線都能唸成一句完整的話。")
    e_rel += notes(rels)

    # --- 階層
    chain = hier.get("chain") or []
    d_h = (f"有效階層 {lv} 層：" + " → ".join(chain)) if chain else f"有效階層 {lv} 層"
    by_level = {}
    for r in rels:
        if r.get("level"):
            by_level.setdefault(int(r["level"]), []).append(_fmt_rel(r))
    if by_level:
        d_h += "\n" + "\n".join(f"第{k}階：{'、'.join(v)}" for k, v in sorted(by_level.items()) if k <= lv)
    rej_h = [f"{x.get('desc')}（{x.get('reason')}）" for x in rejected if x.get("category") == "hierarchy"]
    if rej_h:
        d_h += "\n未計為階層：" + _num(rej_h)
    e_h = [comments.get("hierarchy", ""), hier.get("note", "")]

    # --- 例子
    d_ex = "有效例子：" + _num([f"{e.get('item')}（{e.get('parent')}的例子）" for e in exs])
    rej_e = [f"{x.get('item')}（{x.get('note') or '不是文本中的例子或未連到所屬概念'}）" for x in invalid_ex] + \
            [f"{x.get('desc')}（{x.get('reason')}）" for x in rejected if x.get("category") == "examples"]
    if rej_e:
        d_ex += "\n未計分：" + _num(rej_e)
    e_ex = [comments.get("examples", "")] + notes(exs)

    # --- 交叉連結
    d_cr = "有效交叉連結：" + _num([f"{c.get('a')} ↔ {c.get('b')}" + (f"（{c.get('via')}）" if c.get("via") else "")
                               for c in crs])
    rej_c = [f"{x.get('a')} ↔ {x.get('b')}（{x.get('note') or '不成立'}）" for x in invalid_cr] + \
            [f"{x.get('desc')}（{x.get('reason')}）" for x in rejected if x.get("category") == "cross_links"]
    if rej_c:
        d_cr += "\n未計分：" + _num(rej_c)
    e_cr = [comments.get("cross_links", "")] + [f"「{c.get('a')} ↔ {c.get('b')}」：{c['note']}" for c in crs if c.get("note")]
    if not crs and not comments.get("cross_links"):
        e_cr.append("這張圖目前沒有跨分支的連結。交叉連結是把『不同分支』的概念連起來並說明關係，是概念圖中最能展現統整能力的部分。")

    conflicts = a.get("conflicts") or []
    conflict_txt = ("與文本不一致之處：" + _num(conflicts)) if conflicts else "未發現與文本相違背的內容。"

    def join(parts):
        return "\n".join(p for p in parts if p)

    rows = [
        {"項目": "關係（連結）", "得分細節": d_rel, "得分": f"{counts['relations']} 個 × 1 分 = {pts['relations']} 分",
         "說明": join(e_rel)},
        {"項目": "階層", "得分細節": d_h, "得分": f"{counts['hierarchy']} 層 × 5 分 = {pts['hierarchy']} 分",
         "說明": join(e_h)},
        {"項目": "例子", "得分細節": d_ex, "得分": f"{counts['examples']} 個 × 1 分 = {pts['examples']} 分",
         "說明": join(e_ex)},
        {"項目": "交叉連結", "得分細節": d_cr, "得分": f"{counts['cross']} 個 × 10 分 = {pts['cross']} 分",
         "說明": join(e_cr)},
        {"項目": "總分", "得分細節": conflict_txt, "得分": f"{total} 分", "說明": ""},
    ]
    return {"counts": counts, "pts": pts, "total": total, "rows": rows,
            "unlabeled": len(unlabeled), "not_counted": len(not_counted) + len(rej_e) + len(rej_c) + len(rej_h)}


# ---------------------------------------------------------------- 貢獻值
def _concept_nodes(analysis):
    """非例子的概念節點 id 集合。"""
    ids = set()
    for n in analysis.get("nodes") or []:
        if not n.get("example") and n.get("valid", True):
            ids.add(str(n.get("id")).strip())
    if not ids:
        for r in _valid(analysis.get("relations")):
            ids.update([str(r.get("a")).strip(), str(r.get("b")).strip()])
        for c in _valid(analysis.get("cross_links")):
            ids.update([str(c.get("a")).strip(), str(c.get("b")).strip()])
    ex_items = {str(e.get("item")).strip() for e in _valid(analysis.get("examples"))}
    return ids - ex_items - {""}


def contribution(collab, individuals, settings, standard_score=None):
    """collab: 協作圖判讀；individuals: {seat: 個人圖判讀}。回傳 (各成員結果, 小組摘要)。

    協作個人貢獻分數 C = Σ w_i·D_i，五個維度：
      D1 概念數量、D2 關係鏈品質、D3 層次構建、D4 交叉創新、D5 實例準確性
    每個維度 = 協作圖上以該生顏色實際畫出的有效項目
             + 補登（個人圖上有效、但協作圖上沒有呈現的項目 × 補登係數）
    D1 另加『圈選認同』：該生用自己的顏色圈起別人寫的概念 × 圈選係數。
    """
    w = {k: float(settings.get(k, d)) for k, d in
         [("w_concepts", 0.5), ("w_relations", 1), ("w_hierarchy", 5), ("w_cross", 10), ("w_examples", 1)]}
    s = float(settings.get("supplement_coef", 1.0))
    ring_c = float(settings.get("ring_coef", 0.5))
    seats = list(individuals.keys())
    n = max(len(seats), 1)

    c_rel = _valid(collab.get("relations"))
    c_ex = _valid(collab.get("examples"))
    c_cr = _valid(collab.get("cross_links"))
    c_nodes = [x for x in (collab.get("nodes") or []) if x.get("valid", True) and not x.get("example")]
    ck_rel, ck_ex, ck_cr = {rel_key(r) for r in c_rel}, {ex_key(e) for e in c_ex}, {cross_key(c) for c in c_cr}
    ck_nodes = {str(x.get("id")).strip() for x in c_nodes}
    # 協作圖上的例子節點、以及節點的 covers（一個框內寫了多個概念）也視為「已呈現」
    all_nodes = [x for x in (collab.get("nodes") or []) if x.get("valid", True)]
    ck_nodes_all = ck_nodes | {str(e.get("item")).strip() for e in c_ex} | {str(x.get("id")).strip() for x in all_nodes}
    for x in all_nodes:
        ck_nodes_all |= {str(v).strip() for v in (x.get("covers") or [])}

    T_raw = novak_score(collab)["total"]
    owned_total = sum(1 for x in c_nodes + c_rel + c_ex + c_cr if str(x.get("owner", "")).strip())

    P = {seat: novak_score(a)["total"] for seat, a in individuals.items()}
    P_mean = mean(P.values()) if P else 0

    union_rel, union_ex, union_cr = set(ck_rel), set(ck_ex), set(ck_cr)
    union_levels = {int(r["level"]) for r in c_rel if r.get("level")}
    res = {}
    for seat, a in individuals.items():
        seat = str(seat)
        own = lambda x: str(x.get("owner", "")).strip() == seat  # noqa: E731
        i_rel, i_ex, i_cr = _valid(a.get("relations")), _valid(a.get("examples")), _valid(a.get("cross_links"))
        ik = {rel_key(r) for r in i_rel} | {ex_key(e) for e in i_ex} | {cross_key(c) for c in i_cr}
        a_nodes = [x for x in c_nodes if own(x)]
        a_rel, a_ex, a_cr = [r for r in c_rel if own(r)], [e for e in c_ex if own(e)], [c for c in c_cr if own(c)]
        rings = [x for x in all_nodes if not own(x) and seat in [str(v) for v in (x.get("rings") or [])]]
        s_nodes = sorted(_concept_nodes(a) - ck_nodes_all)
        s_rel = [r for r in i_rel if rel_key(r) not in ck_rel]
        s_ex = [e for e in i_ex if ex_key(e) not in ck_ex]
        s_cr = [c for c in i_cr if cross_key(c) not in ck_cr]
        union_rel |= {rel_key(r) for r in s_rel}
        union_ex |= {ex_key(e) for e in s_ex}
        union_cr |= {cross_key(c) for c in s_cr}
        union_levels |= {int(r["level"]) for r in s_rel if r.get("level")}

        lv_auth = {int(r["level"]) for r in a_rel if r.get("level")}
        lv_supp = {int(r["level"]) for r in s_rel if r.get("level")} - lv_auth
        D = {
            "concepts": len(a_nodes) + s * len(s_nodes) + ring_c * len(rings),
            "relations": len(a_rel) + s * len(s_rel),
            "hierarchy": len(lv_auth) + s * len(lv_supp),
            "cross": len(a_cr) + s * len(s_cr),
            "examples": len(a_ex) + s * len(s_ex),
        }
        C = (w["w_concepts"] * D["concepts"] + w["w_relations"] * D["relations"] + w["w_hierarchy"] * D["hierarchy"]
             + w["w_cross"] * D["cross"] + w["w_examples"] * D["examples"])
        new_items = [x for x in a_rel if rel_key(x) not in ik] + [x for x in a_ex if ex_key(x) not in ik] + \
                    [x for x in a_cr if cross_key(x) not in ik]
        bonus = min(10.0, 1.0 * len(rings) + 2.0 * len(new_items))
        authored_n = len(a_nodes) + len(a_rel) + len(a_ex) + len(a_cr)
        share = authored_n / owned_total if owned_total else 0
        if authored_n and share >= 1.5 / n:
            role = "主導型"
        elif share <= 0.5 / n:
            role = "沉默型"
        else:
            role = "均衡型"
        res[seat] = {
            "D": D, "C": round(C, 2), "P": P[seat], "bonus": bonus, "role": role,
            "share": round(share * 100, 1), "authored_n": authored_n,
            "authored": {"nodes": [x.get("id") for x in a_nodes], "relations": [_fmt_rel(r) for r in a_rel],
                         "examples": [e.get("item") for e in a_ex],
                         "cross": [f"{c.get('a')} ↔ {c.get('b')}" for c in a_cr]},
            "rings": [x.get("id") for x in rings],
            "supplement": {"nodes": s_nodes, "relations": [_fmt_rel(r) for r in s_rel],
                           "examples": [e.get("item") for e in s_ex],
                           "cross": [f"{c.get('a')} ↔ {c.get('b')}" for c in s_cr],
                           "levels": sorted(lv_supp)},
            "new_in_collab": len(new_items),
        }

    ul = 0
    while (ul + 1) in union_levels:
        ul += 1
    T_adj = len(union_rel) * PTS["relations"] + ul * PTS["hierarchy"] + len(union_cr) * PTS["cross"] \
        + len(union_ex) * PTS["examples"]
    std = float(standard_score) if standard_score else float(T_adj or 1)

    # 學習路徑：依個人圖的結構特徵
    stats = {seat: novak_score(a)["counts"] for seat, a in individuals.items()}
    med_h = median([v["hierarchy"] for v in stats.values()]) if stats else 0
    med_r = median([v["relations"] for v in stats.values()]) if stats else 0
    med_e = median([v["examples"] for v in stats.values()]) if stats else 0
    for seat, r in res.items():
        p, c = r["P"], r["C"]
        r["f1"] = round((p * 0.6 + c * 0.4) / T_adj * 100, 1) if T_adj else 0.0
        r["f2"] = round((((c / p) if p else 0) + ((p / P_mean) if P_mean else 0)) / 2 * 100, 1)
        r["f3"] = round((p * 0.4 + c * 0.6 + r["bonus"]) / std * 100, 1) if std else 0.0
        st = stats[seat]
        ex_ratio = st["examples"] / p if p else 0
        if st["examples"] >= med_e and ex_ratio >= 0.15 and st["examples"] > 0:
            r["path"] = "強實例→抽象概念轉化策略"
        elif st["hierarchy"] >= med_h and st["relations"] >= med_r and st["hierarchy"] > 0:
            r["path"] = "強組織力→系統思維訓練"
        else:
            r["path"] = "基礎鷹架→階層與連接詞練習"
    for key in ("f1", "f2", "f3"):
        order = sorted(res, key=lambda k: -res[k][key])
        for i, seat in enumerate(order, 1):
            res[seat][key + "_rank"] = i
    summary = {"T_raw": T_raw, "T_adj": T_adj, "P_mean": round(P_mean, 2), "standard": std,
               "weights": w, "supplement_coef": s, "ring_coef": ring_c, "n": n,
               "union": {"relations": len(union_rel), "levels": ul, "cross": len(union_cr), "examples": len(union_ex)}}
    return res, summary


# ---------------------------------------------------------------- 差異化回饋
def band_of(total, standard):
    r = (total / standard) if standard else 0
    return "進階" if r >= 0.55 else ("發展中" if r >= 0.35 else "起步")


def individual_feedback(name, analysis, score, inventory, standard):
    """個人概念圖回饋：依程度分層，並具體點出『這張圖』的優點、困境與下一步。"""
    inv = inventory or {}
    c, total = score["counts"], score["total"]
    band = band_of(total, standard)
    who = name or "同學"
    strengths = (analysis.get("strengths") or [])[:4]
    weaknesses = (analysis.get("weaknesses") or [])[:4]
    conflicts = analysis.get("conflicts") or []
    have = _concept_nodes(analysis) | {str(e.get("item")) for e in _valid(analysis.get("examples"))}
    core = [x for x in (inv.get("concepts") or []) if x.get("importance") == "core"]
    missing = [x.get("id") for x in core if not ({x.get("id")} | set(x.get("aliases") or [])) & have][:5]
    root = analysis.get("root") or inv.get("root") or "主概念"

    opening = {
        "進階": f"{who}，你的概念圖很有架構！共畫出 {c['relations']} 個有效連結、{c['hierarchy']} 個階層、"
              f"{c['examples']} 個例子、{c['cross']} 個交叉連結，總分 {total} 分，看得出來你把文本讀得很仔細。",
        "發展中": f"{who}，你已經抓到文本的主要骨架了：{c['relations']} 個有效連結、{c['hierarchy']} 個階層、"
               f"{c['examples']} 個例子，總分 {total} 分。再補上幾個地方，這張圖會完整很多。",
        "起步": f"{who}，謝謝你認真完成這張圖！你已經畫出 {c['relations']} 個有效連結、{c['hierarchy']} 個階層、"
              f"{c['examples']} 個例子（總分 {total} 分），這是很好的起點，我們一步一步把它長大。",
    }[band]
    parts = [opening]
    if strengths:
        parts.append("【你做得好的地方】" + "；".join(strengths) + "。")
    trouble = list(weaknesses)
    if score.get("unlabeled"):
        trouble.append(f"有 {score['unlabeled']} 條連線上沒有寫連接詞，別人看圖時不容易知道兩個概念是什麼關係")
    if conflicts:
        trouble.append("有和文本不一致的地方：" + "、".join(conflicts))
    if trouble:
        parts.append("【目前卡住的地方】" + "；".join(trouble) + "。")
    if missing:
        parts.append("【文本中還沒放進圖裡的重點】" + "、".join(f"「{m}」" for m in missing) + "。")

    steps = []
    if band == "起步":
        steps.append(f"先從「{root}」出發，把大概念放中間（或最上面），越細的概念放越外圈（越下面）")
        if missing:
            steps.append(f"回到文本找出「{missing[0]}」和哪個概念有關，畫一條線並在線上寫 2～4 個字的連接詞（如：分為、具有、例如）")
        steps.append("每畫一條線，就試著把它唸成一句話；唸得通，這條線就是有效的連結")
    elif band == "發展中":
        if score.get("unlabeled"):
            steps.append("把沒有連接詞的線補上連接詞，這是最快讓圖變清楚的方法")
        if missing:
            steps.append("把上面列出的文本重點挑 2 個接到正確的上層概念底下，階層就會再往外長一層")
        if c["examples"] < 3:
            steps.append("替最外層的概念各補一個文本中提到的具體例子")
        steps.append("檢查每個例子、每個性質是不是掛在『對的概念』底下")
    else:
        if c["cross"] == 0:
            hints = inv.get("cross_hints") or []
            steps.append("挑戰交叉連結：找出兩個不同分支中彼此有關的概念，畫一條線並寫清楚關係"
                         + (f"（提示：{hints[0]}）" if hints else ""))
        if score.get("unlabeled"):
            steps.append("替每條線補上精準的連接詞，讓整張圖可以被別人獨立讀懂")
        if missing:
            steps.append("把尚未納入的文本重點整合進現有分支")
        steps.append("試著用自己的話，把整張圖從主概念講到最外層，檢查有沒有講不順的地方")
    parts.append("【下一步可以這樣做】" + "；".join(f"{i}. {t}" for i, t in enumerate(steps, 1)) + "。")
    if inv.get("analogy") and band != "進階":
        parts.append("【幫助理解的小比喻】" + inv["analogy"])
    closing = {"進階": "你已經有很好的統整能力，再往『跨分支的關聯』挑戰看看，老師很期待你的下一版！",
               "發展中": "你離完整的概念圖只差幾步，照上面的建議修改後再上傳一次，分數會明顯進步，加油！",
               "起步": "不用急，每次多加一條唸得通的連結就是進步。修改後再上傳，老師會看見你的成長！"}[band]
    parts.append(closing)
    return "\n".join(parts), band


def contribution_feedback(name, r, summary):
    who = name or "同學"
    au, su = r["authored"], r["supplement"]
    n_auth = r["authored_n"]
    n_supp = len(su["relations"]) + len(su["examples"]) + len(su["cross"])
    n = summary["n"]

    def lst(items, k=4):
        items = [str(x) for x in items]
        return "、".join(items[:k]) + ("…等" if len(items) > k else "")

    drew = []
    if au["nodes"]:
        drew.append(f"寫下概念「{lst(au['nodes'])}」")
    if au["relations"]:
        drew.append(f"畫出連結「{lst(au['relations'], 3)}」")
    if au["examples"]:
        drew.append(f"舉出例子「{lst(au['examples'])}」")
    drew_txt = "；".join(drew) if drew else "還沒有用自己的顏色寫下概念或畫出連線"
    ring_txt = f"，並且圈選認同了 {len(r['rings'])} 個同學寫的概念（{lst(r['rings'])}）" if r["rings"] else ""

    f1 = (f"【公式一 加權平均法】{who} 的貢獻值為 {r['f1']}%（全組第 {r['f1_rank']}/{n} 名）。"
          f"算法：（個人圖 {r['P']} 分 × 0.6 ＋ 協作個人貢獻 {r['C']} 分 × 0.4）÷ 協作圖總分（含補登）{summary['T_adj']} 分。"
          f"在協作圖上，你{drew_txt}{ring_txt}。")
    if n_supp:
        f1 += (f"另外，你個人圖上有 {n_supp} 項有效內容（如：{lst(su['relations'] + su['examples'] + su['cross'], 3)}）"
               "沒有出現在協作圖上，系統已依規則幫你補登為貢獻。下次協作時，記得把這些好內容也畫上去，讓全組都受益。")
    else:
        f1 += "你個人圖上的有效內容都已呈現在協作圖中。"

    ratio = round(r["C"] / r["P"] * 100) if r["P"] else 0
    rel = round(r["P"] / summary["P_mean"] * 100) if summary["P_mean"] else 0
    f2 = (f"【公式二 相對提升法】貢獻值為 {r['f2']}%（全組第 {r['f2_rank']}/{n} 名）。"
          f"它由兩部分平均而成：①你把個人圖的實力帶進協作的程度＝協作貢獻 {r['C']} ÷ 個人圖 {r['P']} ＝ {ratio}%；"
          f"②你的個人圖相對於全組平均（{summary['P_mean']} 分）的水準＝{rel}%。")
    if ratio < 70:
        f2 += "①偏低，代表你會的比你在協作中表現出來的多——你個人圖上的許多內容是由別的同學先畫上協作圖的。下次試著主動認領一個分支來畫。"
    elif ratio > 110:
        f2 += "①超過 100%，代表你在協作時貢獻的比個人圖還多，是很棒的協作表現！也可以回頭把這些新想法補進自己的圖。"
    else:
        f2 += "①接近 100%，代表你把自己會的內容相當完整地帶進了小組。"
    if rel < 80:
        f2 += "②低於平均沒關係，先照個人圖的回饋把階層和連結補起來，這個數字自然會上升。"

    f3 = (f"【公式三 綜合貢獻指數法】貢獻值為 {r['f3']}%（全組第 {r['f3_rank']}/{n} 名）。"
          f"算法：（個人圖 {r['P']} × 0.4 ＋ 協作貢獻 {r['C']} × 0.6 ＋ 協作效益加成 {r['bonus']:g}）÷ 標準分數 {summary['standard']:g}。"
          f"協作效益加成來自：圈選認同同學的概念 {len(r['rings'])} 個（每個 1 分）、"
          f"在協作中畫出個人圖沒有的新內容 {r['new_in_collab']} 項（每項 2 分），上限 10 分。")

    if r["role"] == "主導型":
        g = (f"【分層指導：傾聽整合】協作圖上有 {r['share']}% 的內容出自你的筆，你是這組的重要推手，謝謝你的投入！"
             "下一步的挑戰是『傾聽整合』：動筆前先問一位還沒畫的組員「你的圖上有什麼是我們還沒放的？」，"
             "請他親手畫上去，你負責幫忙檢查連接詞。能帶動全組一起完成，是比自己畫完更高一層的能力。")
    elif r["role"] == "沉默型":
        g = (f"【分層指導：貢獻鷹架】這次協作圖上以你的顏色寫下或畫出的內容比較少（{r['share']}%），"
             + (f"不過你用圈選表達了對 {len(r['rings'])} 個概念的認同，也是參與的一種。" if r["rings"] else "")
             + "其實你的個人圖有不少協作圖上沒有的好內容"
             + (f"（例如：{lst(su['relations'] + su['examples'], 3)}）" if n_supp else "")
             + "。下次可以這樣開始：①先從自己的圖挑『一條』最有把握的連結；②對組員說「我想補這一條」；"
             "③親手畫上去並寫上連接詞。一次一條就很好。")
    else:
        g = (f"【分層指導：穩定貢獻】你在協作圖上的內容佔 {r['share']}%，參與度適中。"
             "下一步可以試著擔任『連結者』：找出兩位同學畫的不同分支之間有什麼關係，補上一條交叉連結。")
    path_txt = {
        "強組織力→系統思維訓練": "【學習路徑：系統思維訓練】你的階層與連結是強項。建議練習：選兩個不同分支的概念，"
                        "問自己「如果其中一個改變，另一個會怎樣？」，把答案畫成交叉連結。",
        "強實例→抽象概念轉化策略": "【學習路徑：抽象概念轉化】你很會舉例。建議練習：把同一類的例子圈起來，"
                         "替它們想一個共同的上位概念或共同性質，寫成一個新的節點，讓例子『升級』成概念。",
        "基礎鷹架→階層與連接詞練習": "【學習路徑：階層與連接詞】建議練習：先把文本中的概念依『大→小』排成三層，"
                          "再用「分為、具有、例如」這三種連接詞把它們接起來。",
    }.get(r["path"], "")
    return f1, f2, f3, g + "\n" + path_txt
