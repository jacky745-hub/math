from __future__ import annotations

from .models import DetectedIssue, HintLevel, ScaffoldTurn


def _top_issue(issues: list[DetectedIssue]) -> DetectedIssue | None:
    return issues[0] if issues else None


def build_scaffold(
    problem_text: str,
    issues: list[DetectedIssue],
    is_correct: bool | None,
) -> list[ScaffoldTurn]:
    """
    Create a warm, low-noise, scaffolded hint path.
    Keep each step short, actionable, and metacognitive.
    """
    focus = _top_issue(issues)
    focus_line = ""
    if focus:
        focus_line = f"我先抓一個最可能卡住你的點：**{focus.misconception}**。"

    if is_correct is True:
        # Still scaffold metacognition (how to generalize).
        return [
            ScaffoldTurn(
                level=HintLevel.L0,
                title="做得好，我們把它變成可複製的方法",
                message=(
                    "你的答案看起來是對的。\n\n"
                    "現在用 30 秒，把解法變成『下次也用得上』的步驟。"
                ),
                metacognition_prompt="你覺得這題的關鍵決策點是哪一步？為什麼你選那樣做？",
            ),
            ScaffoldTurn(
                level=HintLevel.L1,
                title="快速檢查（降低粗心）",
                message="把你的答案代回去或用另一種方法驗算一次（只做最短的那種）。",
                metacognition_prompt="如果要避免粗心，你會檢查哪一行？你最常在哪裡出錯？",
            ),
        ]

    return [
        ScaffoldTurn(
            level=HintLevel.L0,
            title="先停一下：把題目變簡單",
            message=(
                "我會陪你一步一步來。\n\n"
                "先不要急著算，先做兩件事：\n"
                "1) 用一句話說『題目要你求什麼』\n"
                "2) 把已知條件圈出來（或用自己的話重寫一次）\n\n"
                f"{focus_line}".strip()
            ),
            metacognition_prompt="你卡住的感覺是：看不懂題目、算到一半亂掉、還是答案怪怪的？",
        ),
        ScaffoldTurn(
            level=HintLevel.L1,
            title="方向提示：先決定用哪一類方法",
            message=(
                "想一下：這題是在做『等式求解』、還是『化簡/運算』、還是『比例/幾何/應用題建模』？\n"
                "你先選一個類別，我再把下一步縮得更小。"
            ),
            metacognition_prompt="你是怎麼判斷題目屬於哪一類的？題目裡哪個詞或符號給你線索？",
        ),
        ScaffoldTurn(
            level=HintLevel.L2,
            title="策略提示：把步驟切成小塊（降低認知負荷）",
            message=(
                "把解題拆成 3 個小任務：\n"
                "- 任務 A：把式子整理乾淨（括號、同類項、分數）\n"
                "- 任務 B：一步一步做等量變形（每一步只做一件事）\n"
                "- 任務 C：回代檢查（找出哪一步開始偏掉）\n\n"
                "你現在最需要的是 A、B、還是 C？"
            ),
            metacognition_prompt="如果只能回頭檢查『一行』，你會選哪一行？為什麼？",
        ),
        ScaffoldTurn(
            level=HintLevel.L3,
            title="微步驟示範：只做『第一小步』",
            message=(
                "我先示範『第一小步』的樣子：\n"
                "- 先把你最容易錯的地方標記出來（例如負號、括號、分母）\n"
                "- 然後只做一個操作（例如兩邊同加 3、或先展開括號）\n\n"
                "你把你打算做的『第一小步』用一句話寫出來，我幫你確認這一步是否安全。"
            ),
            metacognition_prompt="你做這一步前，有沒有先預測『符號/大小』會怎麼變？",
        ),
        ScaffoldTurn(
            level=HintLevel.L4,
            title="接近答案：用檢查把錯抓出來",
            message=(
                "現在用『回代檢查』抓錯：\n"
                "- 把你目前的答案/中間式代回原題\n"
                "- 如果不相等，錯通常在『最近一次變形』\n\n"
                "把你覺得最可疑的那一步貼出來（或描述那一步做了什麼），我會指出可能的錯點。"
            ),
            metacognition_prompt="這次的錯比較像『概念沒釐清』還是『算術粗心』？你怎麼知道？",
        ),
    ]

