// 從 Firebase Console → 專案設定 → 一般 → 你的應用程式 取得這組設定
// （或請 Claude 用 MCP 工具 firebase_get_sdk_config 幫你取得）
// apiKey 等值是設計給前端公開使用的，可以放心提交到 Git。
export const firebaseConfig = {
  apiKey: "YOUR_API_KEY",
  authDomain: "YOUR_PROJECT_ID.firebaseapp.com",
  projectId: "YOUR_PROJECT_ID",
  storageBucket: "YOUR_PROJECT_ID.firebasestorage.app",
  messagingSenderId: "YOUR_SENDER_ID",
  appId: "YOUR_APP_ID",
};
