/* 小安 Xiao-An — Windows 本機版 bridge.
   When the page is served by windows/xiaoan_local.py, a token meta tag is present and these
   extra abilities light up: PowerPoint control, local Word open/save, Spotify app, local files, R.
   Every action still goes through XA.confirm first. Without the helper this file does nothing. */
(function () {
  var XA = window.XA, h = XA.h;
  var meta = document.querySelector('meta[name="xa-local-token"]');
  XA.local = null;

  XA.localCall = function (action, body) {
    if (!meta) return Promise.reject(new Error("沒有連上 Windows 本機版"));
    return fetch("api/" + action, {
      method: "POST",
      headers: { "content-type": "application/json", "X-XA-Token": meta.content },
      body: JSON.stringify(body || {})
    }).then(function (r) {
      return r.json().catch(function () { return {}; }).then(function (j) {
        if (!r.ok) throw new Error(j.error || ("HTTP " + r.status));
        return j;
      });
    });
  };
  XA.blobToBase64 = function (blob) {
    return new Promise(function (resolve, reject) {
      var fr = new FileReader();
      fr.onload = function () { resolve(String(fr.result).split(",")[1] || ""); };
      fr.onerror = reject;
      fr.readAsDataURL(blob);
    });
  };
  function b64ToFile(b64, name) {
    var bin = atob(b64), bytes = new Uint8Array(bin.length);
    for (var i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
    return new File([bytes], name);
  }

  /* ---------- PowerPoint ---------- */
  var P = { status: "", files: [], words: [], all: [] };
  function pptStatus(r) {
    if (r.showing) P.status = "放映中：第 " + (r.slide || "?") + " / " + (r.total || "?") + " 頁";
    else if (r.presentations) P.status = "已開啟" + (r.name ? "「" + r.name + "」" : "簡報") + (r.total ? "，共 " + r.total + " 頁" : "") + "，尚未放映";
    else P.status = "沒有開啟的簡報";
    var el = document.getElementById("ppt-status"); if (el) el.textContent = P.status;
    return r;
  }
  XA.ppt = function (cmd, extra) {
    var labels = { start: "開始放映", next: "下一頁", prev: "上一頁", goto: "跳頁", end: "結束放映", status: "查詢" };
    return XA.localCall("ppt", Object.assign({ cmd: cmd }, extra || {})).then(pptStatus)
      .then(function (r) { if (cmd !== "status") XA.log("sys", "簡報：" + labels[cmd] + "（" + P.status + "）"); return r; })
      .catch(function (e) { XA.toast(e.message); });
  };
  XA.pptOpen = function (path) {
    if (!path) { XA.toast("請先選擇或貼上簡報的路徑。"); return; }
    return XA.confirm("用 PowerPoint 開啟這份簡報？", path, "開啟").then(function (yes) {
      if (!yes) return;
      XA.setState("thinking", "小安正在開啟簡報…");
      return XA.ppt("open", { path: path }).then(function (r) { XA.setState("idle"); if (r) XA.say("簡報開好了。說「開始放映」就可以開始。"); });
    });
  };

  function loadLists() {
    return Promise.all([XA.localCall("list", { kind: "ppt" }), XA.localCall("list", { kind: "word" }), XA.localCall("list", {})])
      .then(function (r) { P.files = r[0].files; P.words = r[1].files; P.all = r[2].files; })
      .catch(function () { /* lists are a convenience */ });
  }

  function pickPath(list, id, placeholder) {
    var inp = h("input", { id: id, class: "input", placeholder: placeholder, style: { width: "100%" } });
    var sel = h("select", { class: "input", style: { width: "100%" }, onchange: function (e) { inp.value = e.target.value; } },
      h("option", { value: "" }, list.length ? "選擇最近的檔案…" : "（桌面、文件、下載裡沒有找到）"),
      list.map(function (f) { return h("option", { value: f.path }, f.name + "　—　" + f.folder); }));
    return { el: h("div", { class: "xa-stack", style: { gap: "8px", marginBottom: "12px" } }, sel, inp), input: inp };
  }

  function localPanel() {
    var ppt = pickPath(P.files, "ppt-path", "或貼上路徑，例如 C:\\Users\\老師\\Desktop\\自由落體.pptx");
    var n = h("input", { class: "input", type: "number", min: 1, value: 1, style: { width: "72px" }, "aria-label": "頁碼" });
    var spotify = h("input", { class: "input", value: (XA.toolsState && XA.toolsState.spotify) || "古典音樂 專注" });
    var file = pickPath(P.all, "file-path", "或貼上檔案路徑");
    return h("div", { class: "panel", style: { marginBottom: "24px", borderColor: "var(--brand)" } },
      h("h3", null, "Windows 本機控制"),
      h("p", { class: "xa-caption", style: { marginBottom: "12px" } }, "小安可以直接操作這台電腦上的 PowerPoint、開啟 Spotify App 與本機檔案。快捷鍵：Page Down／Page Up 換頁。"),
      h("div", { class: "grid2" },
        h("div", null,
          h("p", { class: "field", style: { marginBottom: "4px" } }, "PowerPoint 簡報"), ppt.el,
          h("div", { class: "toolbar" },
            h("button", { class: "xa-btn xa-btn-secondary", onclick: function () { XA.pptOpen(ppt.input.value.trim()); } }, "開啟簡報"),
            h("button", { class: "xa-btn xa-btn-primary", onclick: function () { XA.ppt("start"); } }, "開始放映"),
            h("button", { class: "xa-btn xa-btn-secondary", onclick: function () { XA.ppt("end"); } }, "結束放映")),
          h("div", { class: "toolbar" },
            h("button", { class: "xa-btn xa-btn-secondary", onclick: function () { XA.ppt("prev"); } }, "← 上一頁"),
            h("button", { class: "xa-btn xa-btn-primary", onclick: function () { XA.ppt("next"); } }, "下一頁 →"),
            h("span", { class: "xa-caption" }, "跳到第"), n, h("span", { class: "xa-caption" }, "頁"),
            h("button", { class: "xa-btn xa-btn-quiet", onclick: function () { XA.ppt("goto", { n: +n.value || 1 }); } }, "跳頁")),
          h("p", { class: "xa-caption", id: "ppt-status", role: "status" }, P.status || "按「開啟簡報」，或先在 PowerPoint 開好簡報。")),
        h("div", null,
          h("div", { class: "field" }, "Spotify App", spotify),
          h("button", { class: "xa-btn xa-btn-secondary", style: { marginBottom: "16px" }, onclick: function () { XA.openSpotify(spotify.value.trim()); } }, "在 Spotify App 播放"),
          h("p", { class: "field", style: { marginBottom: "4px" } }, "開啟本機檔案（PowerPoint、Word、PDF、GeoGebra…）"), file.el,
          h("button", { class: "xa-btn xa-btn-secondary", onclick: function () {
            var p = file.input.value.trim(); if (!p) { XA.toast("請先選擇檔案。"); return; }
            XA.confirm("開啟這個檔案？", p, "開啟").then(function (yes) {
              if (yes) XA.localCall("open", { kind: "file", value: p }).then(function () { XA.log("sys", "已開啟：" + p); }).catch(function (e) { XA.toast(e.message); });
            });
          } }, "開啟檔案"))));
  }

  function docsPanel() {
    var w = pickPath(P.words, "word-path", "或貼上 Word 檔路徑");
    return h("div", { class: "panel", style: { marginBottom: "24px", borderColor: "var(--brand)" } },
      h("h3", null, "從這台電腦開啟 Word"),
      h("p", { class: "xa-caption", style: { marginBottom: "12px" } }, "直接讀取本機檔案；寫入時會另存在原檔同一個資料夾（檔名加上「_小安解題」），不覆蓋原檔。"),
      w.el,
      h("button", { class: "xa-btn xa-btn-primary", onclick: function () {
        var p = w.input.value.trim(); if (!p) { XA.toast("請先選擇 Word 檔。"); return; }
        XA.localCall("file_read", { path: p }).then(function (r) {
          var f = b64ToFile(r.data, r.name);
          if (/\.docx$/i.test(r.name)) return XA.docsLoad(f, r.path);
          return f.text().then(function (t) { XA.toast("文字檔請貼到下方文字框：" + t.slice(0, 20) + "…"); });
        }).catch(function (e) { XA.toast(e.message); });
      } }, "讀取文件"));
  }

  /* ---------- R ---------- */
  XA.localRunR = function (code, out) {
    XA.setState("thinking", "小安正在執行 R…");
    XA.clear(out).appendChild(h("p", { class: "xa-caption" }, "R 執行中…（第一次可能需要安裝套件）"));
    XA.localCall("r", { code: code }).then(function (r) {
      XA.clear(out);
      if (r.png) out.appendChild(h("img", { src: "data:image/png;base64," + r.png, alt: "R 產生的圖表", style: { width: "100%", borderRadius: "12px", marginTop: "8px", background: "#fff" } }));
      var text = (r.stdout || "") + (r.ok ? "" : "\n" + (r.stderr || ""));
      if (text.trim()) out.appendChild(h("pre", { class: "code" }, text.trim()));
      if (!r.ok && !r.png) XA.toast("R 執行失敗，訊息顯示在下方。");
    }).catch(function (e) { XA.clear(out).appendChild(h("p", { class: "xa-caption" }, e.message)); })
      .finally(function () { XA.setState("idle"); });
  };

  /* ---------- wire into the app ---------- */
  function wire() {
    var toolsView = XA.views.tools, docsView = XA.views.docs;
    XA.views.tools = function (root) { toolsView(root); var title = root.querySelector(".view-sub"); title.after(localPanel()); };
    XA.views.docs = function (root) { docsView(root); var title = root.querySelector(".view-sub"); title.after(docsPanel()); };
    XA.openSpotify = function (q) {
      return XA.confirm("在 Spotify App 播放「" + q + "」？", "會開啟這台電腦上的 Spotify 並搜尋；沒有安裝 App 時改開網頁版。", "開啟").then(function (yes) {
        if (yes) return XA.localCall("open", { kind: "spotify", value: q }).then(function (r) { XA.log("sys", "已開啟 " + r.opened); }).catch(function (e) { XA.toast(e.message); });
      });
    };
    XA.preIntents = [
      { re: /^(?:請)?(?:下一頁|下一張|往下翻)/, run: function () { XA.ppt("next"); } },
      { re: /^(?:請)?(?:上一頁|上一張|往回翻)/, run: function () { XA.ppt("prev"); } },
      { re: /跳到第\s*(\d+)\s*[頁張]/, run: function (m) { XA.ppt("goto", { n: +m[1] }); } },
      { re: /開始放映|播放簡報|放映簡報/, run: function () { XA.ppt("start").then(function (r) { if (r) XA.say("開始放映。說「下一頁」我就幫你翻頁。"); }); } },
      { re: /結束放映|停止放映|關閉放映/, run: function () { XA.ppt("end"); } },
      { re: /開啟簡報|打開簡報/, run: function () { XA.go("tools"); XA.say("請在上方選擇要開啟的簡報。"); } }
    ];
    document.addEventListener("keydown", function (e) {
      var tag = (e.target.tagName || "").toLowerCase();
      if (tag === "input" || tag === "textarea" || tag === "select") return;
      if (e.key === "PageDown") { e.preventDefault(); XA.ppt("next"); }
      else if (e.key === "PageUp") { e.preventDefault(); XA.ppt("prev"); }
    });
  }

  if (!meta) return;
  wire();
  XA.localCall("ping").then(function (info) {
    XA.local = info;
    return loadLists();
  }).then(function () {
    var mark = document.querySelector(".brandmark");
    if (mark) mark.appendChild(h("span", { class: "xa-badge xa-badge-brand" }, (XA.local.windows ? "Windows" : XA.local.os) + " 本機版"));
    if (XA.current === "tools" || XA.current === "docs") XA.render();
    XA.log("sys", "已連上本機版：可控制 PowerPoint、開啟本機 Word 與 Spotify App" + (XA.local.r ? "、執行 R" : "") + "。");
  }).catch(function (e) { XA.toast("本機版連線失敗：" + e.message); });
})();
