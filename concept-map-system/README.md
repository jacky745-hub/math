# 國中生協作概念圖評分回饋系統

📍 第一版 BY 桃子腳
👥 製作團隊：張文良(作者_桃子腳國中)、鄭鴻哲(協作_桃子腳國中)、霍建豪(協作_桃子腳國中)、翁正鴻(協作_南港高中)

同組學生在同一頁上傳「文本＋每人單一顏色的個人概念圖＋多色協作概念圖」，系統依 Novak 準則
（關係 1、階層 5、例子 1、交叉連結 10）並對照文本評分，計算個人貢獻值，產生差異化回饋；
後台可管理帳號並把所有歷史資料下載成資料表。

## 啟動

```bash
cd concept-map-api
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
export ADMIN_PASSWORD='自訂admin密碼'        # 不設會自動產生並寫入 instance/admin_initial_password.txt
export ANTHROPIC_API_KEY='sk-ant-...'        # 選填：啟用 AI 自動判讀
gunicorn -w 1 --threads 8 --timeout 600 -b 0.0.0.0:5001 src.main:app
```

前台 `http://主機:5001/`，後台 `http://主機:5001/admin/`。手機瀏覽器「加入主畫面」即為 App（PWA）。
測試：`python -m pytest -q tests`。

## 架構

| 檔案 | 作用 |
|---|---|
| `src/extensions.py` | 全系統唯一的 `db = SQLAlchemy()` |
| `src/main.py` | `create_app()`：設定 → `db.init_app(app)`（只呼叫一次）→ `app_context` 內建表 |
| `src/scoring.py` | Novak 計分、貢獻值五維度與三公式、回饋文字（純函式、決定性） |
| `src/ai_engine.py` | Claude 視覺判讀：圖 → 逐項判讀 JSON（不算分） |
| `src/services.py` | 檔案存檔、判讀快取、評分流程 |
| `src/routes/` | `auth`（註冊/登入/登出）、`front`（上傳/結果）、`admin`（帳號/判讀匯入/設定/匯出） |

前端由 Flask 同源提供，沒有 Vite 開發伺服器，所以沒有 `allowedHosts`、跨網域或連不到 localhost 的問題。

## 評分流程與信度

1. **判讀**：把每張圖轉成逐項清單（每條連結的兩端、連接詞、是否與文本相符、所在階層、協作圖上是誰的顏色…）。
   來源是 AI，或教師在後台「判讀匯入／修正」。圖上沒畫線的不列為連結。
2. **計分**：`scoring.py` 以固定規則計算，不含任何特定文本的內容。
3. **快取**：判讀以「文本雜湊＋圖檔 SHA-256＋頁碼」為鍵保存。同一張圖不論隔多久重傳，都取回同一份判讀，分數與細節完全一致。

## 貢獻值

協作個人貢獻分數 `C = Σ wᵢ·Dᵢ`，預設權重：概念數量 0.5、關係鏈品質 1、層次構建 5、交叉創新 10、實例準確性 1。
每個維度 = 協作圖上以該生顏色畫出的有效項目 + 補登（個人圖有、協作圖沒呈現者 × 補登係數，預設 1）；
概念數量另加「用自己的顏色圈起別人寫的概念」× 0.5。

- 公式一 `(P×0.6 + C×0.4) ÷ 協作圖總分(含補登)`
- 公式二 `[(C÷P) + (P÷全組平均P)] ÷ 2`
- 公式三 `(P×0.4 + C×0.6 + 協作效益加成) ÷ 標準分數`；加成 = 圈選認同數×1 + 協作中新增內容×2，上限 10；標準分數 = 文本標準參考圖的 Novak 分數（可在設定覆寫）

權重、補登係數、標準分數都可在「系統設定」調整。

## 身分

admin ＞ 管理者 ＞ 教師 ＞ 學生。admin 可剔除任何人並指派身分；管理者可剔除教師與學生；教師可看全部小組、匯入判讀、下載資料。
學生自行註冊；教師需註冊碼（系統設定）或由 admin 升級。

## 資料下載（後台 → 資料下載）

Excel（小組／個人與協作圖評分／評分細節／貢獻值／使用者）、各表 CSV、所有原始圖檔 ZIP、逐項判讀 JSON。

## 資料保存

資料庫與上傳檔都在 `CM_DATA_DIR`（預設 `concept-map-api/instance/`，已列入 .gitignore，不會進版控）。
正式使用請部署到有持久磁碟的主機（`Dockerfile`、`render.yaml` 已附），或設定 `DATABASE_URL` 使用 PostgreSQL。
