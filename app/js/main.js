/* 小安 Xiao-An — app shell: navigation, top bar, assistant panel, shortcuts, proactive help. */
(function () {
  var XA = window.XA, h = XA.h;

  var NAV = [
    ["quiz", "課堂互動", "QR 派題・統計・文字雲"],
    ["board", "黑板推導", "逐步推導・動態類題"],
    ["graph", "函數繪圖", "頂點・焦點・準線"],
    ["visual", "視覺投影", "示意圖・浮空字卡"],
    ["docs", "文件共編", "Word 解題・寫回檔案"],
    ["tools", "工具與操控", "簡報・地圖・郵件・音樂"],
    null,
    ["settings", "設定與記憶", "語言模型・習慣・隱私"]
  ];
  XA.viewNames = {}; NAV.forEach(function (n) { if (n) XA.viewNames[n[0]] = n[1]; });
  XA.current = XA.store.get("view", "quiz");
  if (!XA.viewNames[XA.current]) XA.current = "quiz";

  XA.go = function (name) {
    if (!XA.views[name]) return;
    XA.current = name; XA.store.set("view", name);
    XA.render();
    var main = XA.$("#view"); if (main) main.scrollTop = 0;
  };
  XA.render = function () {
    var view = XA.$("#view"); if (!view) return;
    XA.clear(view);
    XA.views[XA.current](view);
    document.querySelectorAll(".nav button[data-view]").forEach(function (b) { b.setAttribute("aria-current", b.dataset.view === XA.current ? "page" : "false"); });
    XA.setState(XA.state);
    document.title = XA.viewNames[XA.current] + "｜小安 Xiao-An";
  };

  XA.setTheme = function (t) {
    XA.settings.theme = t; XA.saveSettings();
    document.documentElement.setAttribute("data-theme", t);
    var b = XA.$("#theme-btn"); if (b) b.textContent = t === "dark" ? "教室模式" : "投影模式";
  };
  XA.toggleFullscreen = function () {
    if (document.fullscreenElement) document.exitFullscreen();
    else if (document.documentElement.requestFullscreen) document.documentElement.requestFullscreen().catch(function () { XA.toast("瀏覽器不允許全螢幕。"); });
  };
  var zoom = 1;
  XA.zoom = function (d) { zoom = d === 0 ? 1 : Math.max(0.7, Math.min(1.8, zoom + d)); XA.$("#view").style.zoom = zoom; };
  XA.projectCurrent = function () {
    var st = XA.$("#view .stage");
    if (!st) { XA.say("這個畫面沒有投影區。"); return; }
    st.classList.add("projecting");
  };

  function shell() {
    var input = h("input", { class: "input", id: "say", placeholder: "對小安說…（例如：派發自由落體的題目）", autocomplete: "off", "aria-label": "對小安說" });
    var mic = h("button", { class: "iconbtn", id: "mic", "aria-pressed": "false", title: "語音輸入（空白鍵）", onclick: function () { XA.listen(XA.handle); } }, "● 說話");
    mic.textContent = "● 說話";
    XA.on("mic", function (on) { mic.setAttribute("aria-pressed", on ? "true" : "false"); mic.textContent = on ? "● 聆聽中" : "● 說話"; });
    var form = h("form", { class: "composer", onsubmit: function (e) { e.preventDefault(); var t = input.value; input.value = ""; XA.handle(t); } },
      input, h("button", { class: "xa-btn xa-btn-primary", type: "submit" }, "送出"));
    var chips = h("div", { class: "chips" }, ["你會什麼", "派發題目", "模擬全班作答", "統計結果", "下一步", "畫 y = x² − 4x + 3", "投影動脈血管"].map(function (c) {
      return h("button", { class: "chip", type: "button", onclick: function () { XA.handle(c); } }, c);
    }));
    var app = h("div", { class: "shell xa" },
      h("header", { class: "topbar" },
        h("div", { class: "brandmark" }, h("span", { class: "xa-status-dot", "aria-hidden": "true" }, "安"), "小安", h("span", { class: "xa-caption", style: { fontWeight: 400 } }, "課堂 AI 助教")),
        XA.statusEl(), mic,
        h("button", { class: "iconbtn", id: "theme-btn", onclick: function () { XA.setTheme(XA.settings.theme === "dark" ? "light" : "dark"); } }, "投影模式"),
        h("button", { class: "iconbtn", onclick: XA.toggleFullscreen, title: "全螢幕（F）" }, "全螢幕")),
      h("nav", { class: "nav", "aria-label": "功能" }, NAV.map(function (n) {
        if (!n) return h("hr");
        return h("button", { "data-view": n[0], onclick: function () { XA.go(n[0]); } }, n[1], h("small", null, n[2]));
      })),
      h("main", { class: "main", id: "view", tabindex: "-1" }),
      h("aside", { class: "side", "aria-label": "小安對話" },
        h("div", { class: "side-head" }, h("b", null, "和小安對話"), h("span", { class: "xa-caption" }, XA.hasLLM() ? "已連上語言模型" : "離線指令模式")),
        h("div", { class: "log", id: "log", "aria-live": "polite" }), chips, form));
    document.body.appendChild(app);
    XA.on("settings", function () { var s = app.querySelector(".side-head .xa-caption"); s.textContent = XA.hasLLM() ? "已連上語言模型" : "離線指令模式"; });
  }

  function keys(e) {
    var tag = (e.target.tagName || "").toLowerCase();
    var typing = tag === "input" || tag === "textarea" || tag === "select" || e.target.isContentEditable;
    if (e.key === "Escape") { document.querySelectorAll(".stage.projecting").forEach(function (s) { s.classList.remove("projecting"); }); return; }
    if (typing || e.metaKey || e.ctrlKey || e.altKey) return;
    if (e.key === "ArrowRight" && XA.current === "board") { e.preventDefault(); XA.boardStep(1); }
    else if (e.key === "ArrowLeft" && XA.current === "board") { e.preventDefault(); XA.boardStep(-1); }
    else if (e.key === "f" || e.key === "F") XA.toggleFullscreen();
    else if (e.key === "p" || e.key === "P") XA.projectCurrent();
    else if (e.key === " " && e.target === document.body) { e.preventDefault(); XA.listen(XA.handle); }
    else if (e.key === "/") { e.preventDefault(); XA.$("#say").focus(); }
  }

  /* proactive assistance */
  function proactive() {
    XA.on("all-answered", function (n) {
      XA.toast("全班 " + n + " 人都作答了，要我統計並分析迷思嗎？", [{ label: "好，統計", variant: "primary", run: XA.quizFinish }]);
      XA.speak("全班都作答了，要我統計嗎？");
    });
    var idle = null;
    function reset() {
      clearTimeout(idle);
      if (!XA.settings.proactive) return;
      idle = setTimeout(function () {
        if (XA.current === "board" && !XA.board.practice) XA.toast("同學看起來在思考，要我出一題類題讓大家練習嗎？", [{ label: "出類題", variant: "primary", run: function () { XA.handle("出一題類題"); } }]);
        else if (XA.current === "docs" && XA.docs.questions.length && !XA.docs.questions.some(function (q) { return q.solution; })) XA.toast("需要我幫你檢查這份文件的題目與數字，並寫出解題過程嗎？", [{ label: "好", variant: "primary", run: XA.docsSolve }]);
      }, 90000);
    }
    ["click", "keydown"].forEach(function (ev) { document.addEventListener(ev, reset, true); });
    reset();
  }

  document.addEventListener("DOMContentLoaded", function () {
    document.documentElement.setAttribute("data-theme", XA.settings.theme === "dark" ? "dark" : "light");
    shell();
    XA.setTheme(XA.settings.theme === "dark" ? "dark" : "light");
    XA.render();
    document.addEventListener("keydown", keys);
    proactive();
    XA.log("xa", "老師好，我是小安。可以打字、按「說話」或空白鍵用說的。說「你會什麼」看看我能幫什麼忙。" + (XA.memory.length ? "\n我記得你" + XA.memory.join("、") + "。" : ""));
    if ("speechSynthesis" in window) speechSynthesis.getVoices();
  });
})();
