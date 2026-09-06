# math

即時文字雲教學工具，使用 [Cloud Firestore](https://firebase.google.com/docs/firestore) 儲存資料。

架構參考「Claude Code 懶人包 #04.5：連接 Firebase 資料庫」。

## 檔案結構

- `public/submit.html` — 學生投稿頁（輸入一個詞並送出）
- `public/display.html` — 公開展示頁（即時文字雲，`onSnapshot` 即時更新）
- `public/firebase-config.js` — 前端 Firebase SDK 設定（目前是佔位值，需替換）
- `firestore.rules` — Firestore 安全規則（白名單：`wordcloud_words` 集合開放讀寫，其餘禁止）
- `firebase.json` — Firebase CLI 設定（規則位置 + hosting 目錄）
- `.firebaserc` — 預設專案 ID（目前是佔位值，需替換）

## 尚待你完成的步驟（需要瀏覽器 / 互動式登入，無法在此遠端環境完成）

1. 到 <https://console.firebase.google.com> 建立一個 Firebase 專案，並啟用 Cloud Firestore（正式版模式）。
2. 把 `.firebaserc` 裡的 `YOUR_FIREBASE_PROJECT_ID` 換成你的實際專案 ID。
3. 在 Firebase Console →「專案設定」→「一般」→「你的應用程式」新增一個 Web App，取得 SDK 設定物件，貼到 `public/firebase-config.js`（或請本機的 Claude Code 用 MCP 工具 `firebase_get_sdk_config` 取得）。
4. 在本機（或你自己的 Claude Code 桌面版）執行：
   ```bash
   npx -y firebase-tools@latest login
   npx -y firebase-tools@latest deploy --only firestore:rules
   ```
5. 想要上線展示，可以用 Firebase Hosting（`firebase deploy --only hosting`）或 GitHub Pages 部署 `public/` 目錄。

完成以上步驟後，開啟 `public/submit.html` 讓學生輸入詞語，`public/display.html` 會即時顯示文字雲。
