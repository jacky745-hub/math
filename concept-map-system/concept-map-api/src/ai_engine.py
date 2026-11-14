"""AI 判讀引擎：用 Claude 視覺能力把『文本』與『手繪概念圖』轉成結構化判讀 JSON。

AI 只負責「看圖列出實際畫出的項目，並逐項對照文本判定是否成立」；
分數一律由 scoring.py 以固定規則計算。判讀結果以內容雜湊快取，重傳同一張圖不會重新判讀。
需要環境變數 ANTHROPIC_API_KEY；未設定時系統改走「教師匯入判讀」流程，不會報錯。
"""
import base64
import json
import mimetypes
import os

MODEL = os.environ.get("CM_AI_MODEL", "claude-opus-5-5")


def available():
    return bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"))


_STR = {"type": "string"}
_BOOL = {"type": "boolean"}
_ARR_S = {"type": "array", "items": _STR}


def _obj(props, required=None):
    return {"type": "object", "properties": props, "required": required or list(props), "additionalProperties": False}


INVENTORY_SCHEMA = _obj({
    "title": _STR, "root": _STR,
    "concepts": {"type": "array", "items": _obj({"id": _STR, "aliases": _ARR_S, "importance": {"type": "string", "enum": ["core", "support"]}})},
    "reference": _obj({"relations": {"type": "integer"}, "levels": {"type": "integer"},
                       "cross_links": {"type": "integer"}, "examples": {"type": "integer"}, "items": _ARR_S}),
    "cross_hints": _ARR_S, "analogy": _STR,
})

_LEVEL = {"anyOf": [{"type": "integer"}, {"type": "null"}]}
MAP_SCHEMA = _obj({
    "root": _STR,
    "nodes": {"type": "array", "items": _obj({"id": _STR, "owner": _STR, "rings": _ARR_S, "covers": _ARR_S, "example": _BOOL, "valid": _BOOL})},
    "relations": {"type": "array", "items": _obj({"a": _STR, "b": _STR, "label": _STR, "valid": _BOOL,
                                                  "level": _LEVEL, "owner": _STR, "note": _STR})},
    "examples": {"type": "array", "items": _obj({"parent": _STR, "item": _STR, "valid": _BOOL, "owner": _STR, "note": _STR})},
    "cross_links": {"type": "array", "items": _obj({"a": _STR, "b": _STR, "via": _STR, "valid": _BOOL, "owner": _STR, "note": _STR})},
    "rejected": {"type": "array", "items": _obj({"category": {"type": "string", "enum": ["relations", "hierarchy", "examples", "cross_links"]},
                                                 "desc": _STR, "reason": _STR})},
    "hierarchy": _obj({"chain": _ARR_S, "note": _STR}),
    "comments": _obj({"relations": _STR, "hierarchy": _STR, "examples": _STR, "cross_links": _STR}),
    "strengths": _ARR_S, "weaknesses": _ARR_S, "conflicts": _ARR_S,
})

SYSTEM = """你是國中自然科的學科專家與概念圖評量者，依 Novak & Gowin 的概念圖計分法判讀學生手繪概念圖。
你的工作只有「判讀」，不計算分數。請先把文本精讀至少三遍並牢記，再逐一檢視圖上的每個節點與每條線。

鐵則（違反任何一條都會造成評分錯誤）：
1. 只記錄圖上「實際畫出」的東西。兩個概念之間必須看得到一條線（或箭頭、明確的短線記號）才算有連結；
   只是寫在旁邊、上下排列、框線相鄰而沒有線，一律不算連結，改列入 rejected 並說明「未畫連線」。
2. 每一條連結都要對照文本判定 valid：兩端概念的關係與文本相符才是 true；與文本無關、與文本矛盾、
   或看不出關係者為 false，並在 note 說明原因。完全與文本無關也不是例子的內容不予計分。
3. 階層：以主概念為第 0 層，由上往下（放射狀圖則由中心往外）判定。relations 的 level 填「子概念所在層數」，
   只有『上位概念→更特殊的下位概念／其屬性』的從屬關係才填數字；同層並列、因果串接、未接回主概念的片段填 null。
4. 例子：必須是具體的事物或事件，且有線連到它所屬的概念，才列入 examples。指向例子的連線不重複列入 relations。
5. 交叉連結：連接「不同分支」的概念且關係成立，才列入 cross_links；同一分支內上下層的線不是交叉連結。
6. 節點 id 一律優先使用「文本概念清單」中的名稱；圖上的同義寫法請對應到清單名稱，清單沒有的才用學生原文。
7. 不確定的字跡不要猜成對學生有利的內容；看不清楚就列入 rejected，原因寫「字跡無法辨識」。
8. comments、strengths、weaknesses 要具體指出這張圖的內容（哪個概念、哪條線），用國中生看得懂、委婉鼓勵的語氣；
   conflicts 只列出與文本相違背之處，沒有就給空陣列。
9. 不得加入圖上沒有的內容，也不得引用本說明或其他圖的內容當作這張圖的得分細節。"""


def _file_block(path, name=""):
    mime = mimetypes.guess_type(name or path)[0] or "application/octet-stream"
    with open(path, "rb") as f:
        data = base64.standard_b64encode(f.read()).decode()
    if mime == "application/pdf":
        return {"type": "document", "source": {"type": "base64", "media_type": mime, "data": data}}
    if mime in ("image/png", "image/jpeg", "image/gif", "image/webp"):
        return {"type": "image", "source": {"type": "base64", "media_type": mime, "data": data}}
    raise ValueError(f"AI 判讀目前支援 PDF、PNG、JPG、GIF、WEBP；此檔案格式（{mime}）請由教師人工判讀後匯入。")


def _call(content, schema):
    import anthropic
    client = anthropic.Anthropic()
    with client.beta.messages.stream(
        model=MODEL, max_tokens=32000, system=SYSTEM,
        thinking={"type": "adaptive"},
        output_config={"effort": "high", "format": {"type": "json_schema", "schema": schema}},
        betas=["server-side-fallback-2026-07-01"], fallbacks="default",
        messages=[{"role": "user", "content": content}],
    ) as stream:
        msg = stream.get_final_message()
    if msg.stop_reason == "refusal":
        raise RuntimeError("AI 拒絕判讀此內容，請改由教師人工判讀。")
    if msg.stop_reason == "max_tokens":
        raise RuntimeError("AI 判讀輸出過長而中斷，請重試或由教師人工判讀。")
    return json.loads(next(b.text for b in msg.content if b.type == "text"))


def build_inventory(text, text_file=None, text_name=""):
    content = []
    if text_file and not text.strip():
        content.append(_file_block(text_file, text_name))
    content.append({"type": "text", "text":
        "以下是學生繪製概念圖所依據的文本。請精讀三遍後輸出：\n"
        "- root：文本的主概念；concepts：文本中所有重要概念（id 用文本原詞、精簡），標示 core/support；\n"
        "- reference：依此文本可畫出的『標準概念圖』中，有效關係數、階層數、交叉連結數、例子數，以及 items 逐條列出；\n"
        "- cross_hints：2～3 個可引導學生發現交叉連結的提示問句；\n"
        "- analogy：一個適合八年級學生、幫助理解本文核心抽象概念的生活類比（一兩句話）。\n\n"
        "【文本】\n" + (text or "（見附檔）")})
    inv = _call(content, INVENTORY_SCHEMA)
    ref = inv.get("reference") or {}
    inv["standard_score"] = ref.get("relations", 0) + 5 * ref.get("levels", 0) + 10 * ref.get("cross_links", 0) + ref.get("examples", 0)
    return inv


def analyze_map(text, inventory, path, name, page, map_type, members=None, seat=None):
    concepts = "、".join(c["id"] for c in inventory.get("concepts", []))
    if map_type == "collab":
        who = "\n".join(f"- 座號 {m['seat']}：{m['color']}" for m in members)
        task = ("這是一張『小組協作概念圖』，每位組員用自己的顏色繪製。組員與顏色如下：\n" + who +
                "\n請依筆跡顏色判定每個節點文字、每條連線、每個例子是誰畫的，owner 填該生座號（無法判定填空字串）。"
                "若某位組員用自己的顏色把別人寫的節點『圈起來』，請把他的座號列入該節點的 rings。")
    else:
        task = f"這是座號 {seat} 學生的『個人概念圖』（單一顏色）。owner 一律填 \"{seat}\"，rings 給空陣列。"
    content = [_file_block(path, name), {"type": "text", "text":
        f"【文本】\n{text}\n\n【文本概念清單（節點 id 請優先使用這些名稱）】\n{concepts}\n\n"
        f"【任務】{task}\n" + (f"檔案有多頁時，只判讀第 {page} 頁。\n" if page else "") +
        "請依系統規則輸出判讀 JSON。"}]
    return _call(content, MAP_SCHEMA)
