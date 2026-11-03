/* 小安 Xiao-An — core: DOM helper, storage, status, voice, confirm, privacy, memory, LLM. */
(function () {
  var XA = (window.XA = window.XA || {});
  XA.views = {};

  /* ---------- DOM ---------- */
  function h(tag, props) {
    var el = tag instanceof Element ? tag : document.createElement(tag);
    props = props || {};
    Object.keys(props).forEach(function (k) {
      var v = props[k];
      if (v == null || v === false) return;
      if (k === "class") el.className = v;
      else if (k === "style" && typeof v === "object") Object.assign(el.style, v);
      else if (k.slice(0, 2) === "on" && typeof v === "function") el.addEventListener(k.slice(2).toLowerCase(), v);
      else if (k === "html") el.innerHTML = v;
      else if (k in el && k !== "list" && typeof v !== "string") el[k] = v;
      else el.setAttribute(k, v === true ? "" : v);
    });
    for (var i = 2; i < arguments.length; i++) append(el, arguments[i]);
    return el;
  }
  function append(el, c) {
    if (c == null || c === false) return;
    if (Array.isArray(c)) return c.forEach(function (x) { append(el, x); });
    el.appendChild(c instanceof Node ? c : document.createTextNode(String(c)));
  }
  var SVGNS = "http://www.w3.org/2000/svg";
  function s(tag, attrs) {
    var el = document.createElementNS(SVGNS, tag);
    Object.keys(attrs || {}).forEach(function (k) { if (attrs[k] != null) el.setAttribute(k, attrs[k]); });
    for (var i = 2; i < arguments.length; i++) {
      var c = arguments[i];
      if (c == null) continue;
      if (Array.isArray(c)) c.forEach(function (x) { if (x) el.appendChild(x); });
      else el.appendChild(c instanceof Node ? c : document.createTextNode(String(c)));
    }
    return el;
  }
  function clear(el) { while (el.firstChild) el.removeChild(el.firstChild); return el; }
  XA.h = h; XA.s = s; XA.clear = clear;
  XA.$ = function (sel, root) { return (root || document).querySelector(sel); };

  /* ---------- storage (never throws) ---------- */
  XA.store = {
    get: function (k, d) { try { var v = localStorage.getItem("xa." + k); return v == null ? d : JSON.parse(v); } catch (e) { return d; } },
    set: function (k, v) { try { localStorage.setItem("xa." + k, JSON.stringify(v)); } catch (e) { /* private mode */ } }
  };
  XA.settings = Object.assign({
    apiKey: "", model: "claude-opus-5-5", voice: true, lang: "zh-TW", relay: false,
    baseUrl: "", theme: "light", proactive: true
  }, XA.store.get("settings", {}));
  XA.saveSettings = function () { XA.store.set("settings", XA.settings); };

  /* ---------- tiny event bus ---------- */
  var subs = {};
  XA.on = function (ev, fn) { (subs[ev] = subs[ev] || []).push(fn); };
  XA.emit = function (ev, data) { (subs[ev] || []).forEach(function (fn) { try { fn(data); } catch (e) { console.error(e); } }); };

  /* ---------- AgentStatus ---------- */
  var LABEL = { idle: "小安待命中", listening: "小安正在聽…", thinking: "小安思考中…", speaking: "小安正在說" };
  XA.statusEl = function () {
    return h("span", { class: "xa-status xa-status-idle", role: "status", "aria-live": "polite", "data-xa-status": "" },
      h("span", { class: "xa-status-dot", "aria-hidden": "true" }, "安"), h("span", { class: "lbl" }, LABEL.idle),
      h("span", { class: "xa-status-bars", "aria-hidden": "true", hidden: true }, h("i", { style: { height: "8px" } }), h("i", { style: { height: "14px" } }), h("i", { style: { height: "10px" } })));
  };
  XA.state = "idle";
  XA.setState = function (st, label) {
    XA.state = st;
    document.querySelectorAll("[data-xa-status]").forEach(function (el) {
      el.className = "xa-status xa-status-" + st;
      el.querySelector(".lbl").textContent = label || LABEL[st];
      el.querySelector(".xa-status-bars").hidden = !(st === "listening" || st === "speaking");
    });
  };

  /* ---------- conversation log ---------- */
  XA.log = function (who, text, actions) {
    var log = document.getElementById("log");
    if (!log) return;
    var m = h("div", { class: "msg " + who }, text);
    if (actions && actions.length) m.appendChild(h("div", { class: "act" }, actions.map(function (a) {
      return h("button", { class: "xa-btn xa-btn-" + (a.variant || "secondary"), style: { padding: "4px 12px" }, onclick: a.run }, a.label);
    })));
    log.appendChild(m);
    log.scrollTop = log.scrollHeight;
    return m;
  };
  /* Xiao-An speaks: logs and (if voice on) reads aloud. */
  XA.say = function (text, actions) {
    XA.log("xa", text, actions);
    XA.speak(text);
  };

  /* ---------- TTS ---------- */
  XA.speak = function (text) {
    if (!XA.settings.voice || !("speechSynthesis" in window)) return;
    try {
      speechSynthesis.cancel();
      var u = new SpeechSynthesisUtterance(String(text).replace(/[*#`]/g, "").slice(0, 400));
      u.lang = XA.settings.lang;
      var v = speechSynthesis.getVoices().filter(function (x) { return x.lang && x.lang.replace("_", "-").indexOf(XA.settings.lang) === 0; })[0];
      if (v) u.voice = v;
      u.onstart = function () { XA.setState("speaking"); };
      u.onend = u.onerror = function () { if (XA.state === "speaking") XA.setState("idle"); };
      speechSynthesis.speak(u);
    } catch (e) { /* no voice */ }
  };

  /* ---------- STT ---------- */
  var Rec = window.SpeechRecognition || window.webkitSpeechRecognition, rec = null;
  XA.canListen = !!Rec;
  XA.listen = function (onText) {
    if (!Rec) { XA.toast("這個瀏覽器不支援語音輸入，請改用 Chrome 或 Edge，或直接打字。"); return; }
    if (rec) { rec.stop(); return; }
    rec = new Rec();
    rec.lang = XA.settings.lang; rec.interimResults = false; rec.maxAlternatives = 1;
    rec.onstart = function () { XA.setState("listening"); XA.emit("mic", true); };
    rec.onresult = function (e) { var t = e.results[0][0].transcript; if (t) onText(t); };
    rec.onerror = function (e) { if (e.error !== "no-speech" && e.error !== "aborted") XA.toast("語音輸入失敗：" + e.error); };
    rec.onend = function () { rec = null; if (XA.state === "listening") XA.setState("idle"); XA.emit("mic", false); };
    try { rec.start(); } catch (e) { rec = null; }
  };

  /* ---------- toast ---------- */
  var toastTimer;
  XA.toast = function (text, actions) {
    var old = document.querySelector(".toast"); if (old) old.remove();
    var t = h("div", { class: "toast", role: "status" }, h("span", { class: "xa-status-dot", style: { width: "28px", height: "28px", display: "grid", placeItems: "center", borderRadius: "999px", background: "var(--brand-soft)", color: "var(--brand)", fontWeight: 700, flex: "none" } }, "安"),
      h("span", { style: { flex: 1, fontSize: "15px" } }, text),
      (actions || []).map(function (a) { return h("button", { class: "xa-btn xa-btn-" + (a.variant || "quiet"), onclick: function () { t.remove(); a.run(); } }, a.label); }),
      h("button", { class: "xa-btn xa-btn-quiet", "aria-label": "關閉", onclick: function () { t.remove(); } }, "✕"));
    document.body.appendChild(t);
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () { t.remove(); }, actions && actions.length ? 15000 : 6000);
  };

  /* ---------- ActionConfirm: every key action waits for the teacher ---------- */
  XA.confirm = function (action, detail, confirmLabel) {
    return new Promise(function (resolve) {
      var prev = document.activeElement;
      function done(v) { scrim.remove(); document.removeEventListener("keydown", onKey); if (prev && prev.focus) prev.focus(); resolve(v); }
      function onKey(e) { if (e.key === "Escape") done(false); }
      var ok = h("button", { class: "xa-btn xa-btn-primary", onclick: function () { done(true); } }, confirmLabel || "確認執行");
      var scrim = h("div", { class: "scrim", onclick: function (e) { if (e.target === scrim) done(false); } },
        h("div", { class: "xa xa-confirm", role: "alertdialog", "aria-modal": "true", "aria-label": action },
          h("div", { class: "xa-confirm-head" }, XA.statusEl()),
          h("p", { class: "xa-title" }, action),
          h("p", { class: "xa-confirm-detail" }, detail),
          h("p", { class: "xa-caption" }, "小安不會在你確認前執行；不會讀取密碼或身分證字號。"),
          h("div", { class: "xa-confirm-actions" }, h("button", { class: "xa-btn xa-btn-secondary", onclick: function () { done(false); } }, "先不要"), ok)));
      document.body.appendChild(scrim);
      scrim.querySelector(".lbl").textContent = "小安等你決定";
      document.addEventListener("keydown", onKey);
      ok.focus();
    });
  };
  XA.openLink = function (action, url, detail) {
    return XA.confirm(action, detail || url).then(function (yes) {
      if (yes) { window.open(url, "_blank", "noopener"); XA.log("sys", "已開啟：" + action); }
      return yes;
    });
  };

  /* ---------- privacy: strip sensitive data before anything leaves the browser ---------- */
  XA.redact = function (text) {
    var hits = 0;
    var out = String(text)
      .replace(/\b[A-Z][12489]\d{8}\b/g, function () { hits++; return "［身分證字號已遮蔽］"; })
      .replace(/((?:密碼|password|passwd|pwd)\s*[:：=]?\s*)\S+/gi, function (m, p) { hits++; return p + "［已遮蔽］"; })
      .replace(/\b(?:sk-ant-|sk-)[A-Za-z0-9_-]{10,}\b/g, function () { hits++; return "［金鑰已遮蔽］"; })
      .replace(/\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b/g, function () { hits++; return "［卡號已遮蔽］"; });
    return { text: out, hits: hits };
  };

  /* ---------- memory: habits learned from conversation ---------- */
  XA.memory = XA.store.get("memory", ["喜歡用生活實例輔助說明"]);
  XA.remember = function (fact) {
    fact = String(fact).trim().replace(/[。.!！]+$/, "");
    if (!fact || XA.memory.indexOf(fact) >= 0) return false;
    XA.memory.push(fact); XA.store.set("memory", XA.memory); XA.emit("memory");
    return true;
  };
  XA.forget = function (i) { XA.memory.splice(i, 1); XA.store.set("memory", XA.memory); XA.emit("memory"); };
  XA.likesExamples = function () { return XA.memory.some(function (m) { return /生活|實例|例子/.test(m); }); };

  /* ---------- LLM (optional): Claude Messages API, called from the browser ---------- */
  XA.hasLLM = function () { return !!XA.settings.apiKey; };
  XA.systemPrompt = function (extra) {
    return [
      "你是「小安」，台灣國中課堂的 AI 助教。用繁體中文（台灣用語、全形標點）回答，句子短、口語、一句一個重點，不用 emoji、不用 Markdown 標題。",
      "解釋迷思概念時，先說學生可能的想法來源，再給一個生活例子。數字用阿拉伯數字並附單位。",
      "絕不要求或處理帳號密碼、身分證字號等個資。任何寄信、存檔、切換畫面等動作，只能建議，由老師決定。",
      XA.memory.length ? "你記得這位老師的習慣：" + XA.memory.join("；") + "。請自動套用。" : "",
      extra || ""
    ].filter(Boolean).join("\n");
  };
  XA.ask = function (userText, opts) {
    opts = opts || {};
    if (!XA.hasLLM()) return Promise.reject(new Error("NO_KEY"));
    var r = XA.redact(userText);
    if (r.hits) XA.log("sys", "已在送出前遮蔽 " + r.hits + " 筆敏感資訊。");
    XA.setState("thinking");
    var history = (opts.history || []).concat([{ role: "user", content: r.text }]);
    return fetch("https://api.anthropic.com/v1/messages", {
      method: "POST",
      headers: {
        "content-type": "application/json",
        "x-api-key": XA.settings.apiKey,
        "anthropic-version": "2023-06-01",
        "anthropic-dangerous-direct-browser-access": "true"
      },
      body: JSON.stringify({ model: XA.settings.model, max_tokens: opts.maxTokens || 1500, system: XA.systemPrompt(opts.system), messages: history })
    }).then(function (res) {
      return res.json().then(function (j) {
        if (!res.ok) throw new Error((j.error && j.error.message) || ("HTTP " + res.status));
        return (j.content || []).filter(function (b) { return b.type === "text"; }).map(function (b) { return b.text; }).join("\n").trim();
      });
    }).finally(function () { if (XA.state === "thinking") XA.setState("idle"); });
  };
  XA.askOrExplain = function (text, opts) {
    return XA.ask(text, opts).catch(function (e) {
      if (e.message === "NO_KEY") {
        XA.say("這件事需要連上語言模型。請到「設定與記憶」貼上 Claude API 金鑰，我就能幫你。");
      } else {
        XA.say("連線語言模型失敗：" + e.message);
      }
      return null;
    });
  };

  /* ---------- helpers ---------- */
  XA.round = function (x, d) { var p = Math.pow(10, d == null ? 2 : d); return Math.round(x * p) / p; };
  XA.uid = function (n) { var a = "ABCDEFGHJKMNPQRSTUVWXYZ23456789", o = ""; for (var i = 0; i < (n || 4); i++) o += a[Math.floor(Math.random() * a.length)]; return o; };
  XA.shuffle = function (arr) { var a = arr.slice(); for (var i = a.length - 1; i > 0; i--) { var j = Math.floor(Math.random() * (i + 1)); var t = a[i]; a[i] = a[j]; a[j] = t; } return a; };
  XA.b64e = function (obj) { return btoa(unescape(encodeURIComponent(JSON.stringify(obj)))).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, ""); };
  XA.b64d = function (str) { str = str.replace(/-/g, "+").replace(/_/g, "/"); while (str.length % 4) str += "="; return JSON.parse(decodeURIComponent(escape(atob(str)))); };
  XA.download = function (name, blob) {
    var a = h("a", { href: URL.createObjectURL(blob), download: name });
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(function () { URL.revokeObjectURL(a.href); }, 2000);
  };
})();
