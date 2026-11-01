/* 小安 Xiao-An — 課堂即時互動與測驗派發: QR quiz, live responses, stats, misconception analysis, word cloud. */
(function () {
  var XA = window.XA, h = XA.h;

  var BANK = [
    { id: "fall", type: "single", topic: "自由落體",
      stem: "一顆球從 20 公尺高處自由落下（g = 9.8 m/s²），大約幾秒落地？",
      options: [
        { label: "A", text: "1 秒" },
        { label: "B", text: "約 2 秒", correct: true },
        { label: "C", text: "4 秒", misconception: "直接把高度除以 5，把公式背成「時間＝高度÷5」，沒有用到 H = ½gt²" },
        { label: "D", text: "要看球多重", misconception: "以為越重的東西掉得越快，這是很自然的生活直覺，但忽略了空氣阻力很小時，落下快慢和質量無關" }],
      example: "從 7 樓窗台同時放開橡皮擦和鉛筆盒，它們幾乎同時落地。" },
    { id: "vertex", type: "single", topic: "二次函數",
      stem: "二次函數 y = x² − 4x + 3 的頂點座標是？",
      options: [
        { label: "A", text: "(2, −1)", correct: true },
        { label: "B", text: "(−2, −1)", misconception: "配方時 −4x 的符號沒處理好，頂點 x 座標應是 −b/2a = 2" },
        { label: "C", text: "(4, 3)" },
        { label: "D", text: "(2, 3)", misconception: "找到對稱軸 x = 2 後，忘了代回原式求 y" }],
      example: "就像投籃的球，最高點那一刻的「位置」和「高度」要一起說，才知道球在哪裡。" },
    { id: "artery", type: "multi", topic: "循環系統",
      stem: "下列哪些是動脈管壁的構造？（多選）",
      options: [
        { label: "A", text: "內膜", correct: true },
        { label: "B", text: "中膜", correct: true },
        { label: "C", text: "外膜", correct: true },
        { label: "D", text: "瓣膜", misconception: "把靜脈裡防止血液倒流的瓣膜，和動脈管壁的三層構造混在一起" }],
      example: "動脈像有彈性的水管，三層管壁讓它撐得住心臟一下一下的壓力。" },
    { id: "open-fall", type: "open", topic: "自由落體",
      stem: "你覺得什麼會影響物體落地所需的時間？用一句話寫下你的想法。", options: [],
      pool: ["高度越高越久", "重力", "重量越重越快", "空氣阻力", "物體的形狀", "高度和重力", "質量", "風的大小", "初速度", "地球引力", "看高度", "重的比較快", "空氣阻力和形狀", "掉落的高度", "重力加速度"] }
  ];
  XA.quizBank = BANK;

  var state = { draft: clone(BANK[0]), session: null, responses: {}, stop: null, showResults: false, insight: "" };
  XA.quiz = state;
  function clone(o) { return JSON.parse(JSON.stringify(o)); }

  /* ---------- editor ---------- */
  function editor() {
    var d = state.draft;
    var optsBox = h("div");
    function renderOpts() {
      XA.clear(optsBox);
      if (d.type === "open") { optsBox.appendChild(h("p", { class: "xa-caption" }, "開放式回應會即時整理成文字雲。")); return; }
      d.options.forEach(function (o, i) {
        optsBox.appendChild(h("div", { class: "opt-row" },
          h("b", null, o.label),
          h("input", { class: "input", value: o.text, "aria-label": "選項 " + o.label, oninput: function (e) { o.text = e.target.value; } }),
          h("input", { class: "input", value: o.misconception || "", placeholder: o.correct ? "（正解）" : "選這個的可能迷思（選填）", "aria-label": "選項 " + o.label + " 的迷思", disabled: !!o.correct,
            oninput: function (e) { o.misconception = e.target.value; } }),
          h("label", null, h("input", { type: "checkbox", checked: !!o.correct, onchange: function (e) {
            if (d.type === "single") d.options.forEach(function (x) { x.correct = false; });
            o.correct = e.target.checked; if (o.correct) o.misconception = ""; renderOpts();
          } }), "正解")));
        if (i === d.options.length - 1) optsBox.appendChild(h("div", { class: "row" },
          d.options.length < 6 ? h("button", { class: "xa-btn xa-btn-quiet", onclick: function () { d.options.push({ label: "ABCDEF"[d.options.length], text: "" }); renderOpts(); } }, "＋ 新增選項") : null,
          d.options.length > 2 ? h("button", { class: "xa-btn xa-btn-quiet", onclick: function () { d.options.pop(); renderOpts(); } }, "－ 移除最後一項") : null));
      });
    }
    renderOpts();
    return h("div", { class: "panel" },
      h("h3", null, "出題"),
      h("div", { class: "row" },
        h("div", { class: "field" }, "題庫",
          h("select", { onchange: function (e) { var b = BANK.filter(function (x) { return x.id === e.target.value; })[0]; if (b) { state.draft = clone(b); XA.render(); } } },
            BANK.map(function (b) { return h("option", { value: b.id, selected: b.id === d.id }, b.topic + "・" + ({ single: "單選", multi: "多選", open: "觀念思考" })[b.type]); }),
            h("option", { value: "", selected: !BANK.some(function (b) { return b.id === d.id; }) }, "（自訂）"))),
        h("div", { class: "field" }, "題型",
          h("select", { onchange: function (e) {
            d.type = e.target.value; d.id = "custom";
            if (d.type !== "open" && d.options.length < 2) d.options = ["A", "B", "C", "D"].map(function (l) { return { label: l, text: "" }; });
            if (d.type === "single") { var first = true; d.options.forEach(function (o) { if (o.correct && !first) o.correct = false; if (o.correct) first = false; }); }
            XA.render();
          } }, [["single", "單選題"], ["multi", "多選題"], ["open", "觀念思考題"]].map(function (t) { return h("option", { value: t[0], selected: d.type === t[0] }, t[1]); })))),
      h("div", { class: "field" }, "題目",
        h("textarea", { rows: 2, oninput: function (e) { d.stem = e.target.value; d.id = d.id === "custom" ? d.id : d.id; } }, d.stem)),
      optsBox,
      h("div", { class: "field" }, "生活實例（小安解說時使用，選填）", h("input", { value: d.example || "", oninput: function (e) { d.example = e.target.value; } })),
      h("div", { class: "row" },
        h("button", { class: "xa-btn xa-btn-primary", onclick: function () { XA.quizDispatch(); } }, "派發題目"),
        h("button", { class: "xa-btn xa-btn-secondary", onclick: aiVariant }, "讓小安出類題")));
  }

  function validate(d) {
    if (!d.stem || !d.stem.trim()) return "請先寫題目。";
    if (d.type === "open") return null;
    if (d.options.some(function (o) { return !o.text.trim(); })) return "還有選項是空的。";
    if (!d.options.some(function (o) { return o.correct; })) return "請勾選至少一個正解。";
    return null;
  }

  /* ---------- dispatch ---------- */
  XA.quizDispatch = function (quiz) {
    if (quiz) state.draft = clone(quiz);
    var err = validate(state.draft);
    if (err) { XA.toast(err); return; }
    if (state.stop) state.stop();
    var code = XA.uid(4);
    var topic = XA.settings.relay ? XA.relay.topic(code, XA.uid(8).toLowerCase()) : null;
    state.session = { code: code, quiz: clone(state.draft), topic: topic, startedAt: Date.now() };
    state.responses = {}; state.showResults = false; state.insight = "";
    state.stop = XA.relay.listen(state.session, onAnswer);
    XA.go("quiz");
    XA.say("題目已派發，代碼 " + code + "。請同學掃描 QR Code 作答。");
  };

  function onAnswer(a) {
    if (!state.session || a.code !== state.session.code || !a.sid) return;
    var q = state.session.quiz;
    if (q.type === "open") { if (typeof a.answer !== "string" || !a.answer.trim()) return; a.answer = a.answer.slice(0, 80); }
    else {
      var valid = q.options.map(function (o) { return o.label; });
      var arr = [].concat(a.answer).filter(function (x) { return valid.indexOf(x) >= 0; });
      if (!arr.length) return;
      a.answer = q.type === "single" ? arr[0] : arr;
    }
    var before = Object.keys(state.responses).length;
    state.responses[a.sid] = a.answer;
    updateLive();
    var n = Object.keys(state.responses).length, exp = XA.store.get("classSize", 30);
    if (XA.settings.proactive && before < exp && n >= exp && !state.showResults) XA.emit("all-answered", n);
  }

  XA.quizStudentUrl = function () {
    var s = state.session; if (!s) return "";
    var q = s.quiz;
    var payload = { c: s.code, t: q.type, s: q.stem, o: q.options.map(function (o) { return [o.label, o.text]; }), r: s.topic || "" };
    var base = XA.settings.baseUrl || location.href.replace(/[#?].*$/, "").replace(/[^/]*$/, "");
    if (!/\/$/.test(base)) base += "/";
    return base + "student.html#" + XA.b64e(payload);
  };

  function qrSvg(text) {
    try {
      var qr = qrcode(0, "M"); qr.addData(text); qr.make();
      var wrap = h("div", { html: qr.createSvgTag({ cellSize: 4, margin: 0, scalable: true }) });
      var svg = wrap.firstChild; svg.setAttribute("role", "img"); svg.setAttribute("aria-label", "掃描作答 QR Code");
      return svg;
    } catch (e) { return h("p", { class: "xa-caption" }, "QR Code 產生失敗：網址太長，請縮短題目。"); }
  }

  XA.quizFinish = function () {
    if (!state.session) { XA.say("還沒有派發題目。"); return; }
    state.showResults = true; XA.go("quiz"); XA.say(XA.quizInsight());
  };
  XA.quizSimulate = function (n) { if (state.session) { simulate(n || 30); } };

  /* ---------- simulate a class (demo / rehearsal) ---------- */
  function simulate(n) {
    var q = state.session.quiz; n = n || 30;
    for (var i = 0; i < n; i++) {
      var sid = "sim-" + XA.uid(6), ans;
      if (q.type === "open") ans = q.pool ? q.pool[Math.floor(Math.random() * q.pool.length)] : "（模擬回答）";
      else {
        var weights = q.options.map(function (o) { return o.correct ? 26 : (o.misconception ? 40 / q.options.filter(function (x) { return x.misconception; }).length : 8); });
        if (q.type === "multi") {
          ans = q.options.filter(function (o, k) { return Math.random() < (o.correct ? 0.75 : (o.misconception ? 0.45 : 0.15)); }).map(function (o) { return o.label; });
          if (!ans.length) ans = [q.options[0].label];
        } else {
          var sum = weights.reduce(function (a, b) { return a + b; }, 0), r = Math.random() * sum, k = 0;
          while (r > weights[k]) { r -= weights[k]; k++; }
          ans = q.options[Math.min(k, q.options.length - 1)].label;
        }
      }
      onAnswer({ kind: "answer", code: state.session.code, sid: sid, answer: ans });
    }
  }

  /* ---------- statistics ---------- */
  XA.quizStats = function () {
    var s = state.session; if (!s) return null;
    var q = s.quiz, answers = Object.keys(state.responses).map(function (k) { return state.responses[k]; });
    var total = answers.length;
    if (q.type === "open") return { total: total, words: cloudWords(answers) };
    var correctSet = q.options.filter(function (o) { return o.correct; }).map(function (o) { return o.label; }).sort().join(",");
    var counts = {}; q.options.forEach(function (o) { counts[o.label] = 0; });
    var right = 0;
    answers.forEach(function (a) {
      [].concat(a).forEach(function (l) { counts[l]++; });
      if ([].concat(a).slice().sort().join(",") === correctSet) right++;
    });
    var wrong = q.options.filter(function (o) { return !o.correct; }).sort(function (a, b) { return counts[b.label] - counts[a.label]; })[0];
    return { total: total, counts: counts, right: right, rate: total ? Math.round(right / total * 100) : 0, topWrong: wrong && counts[wrong.label] ? wrong : null };
  };

  var STOP = ["的", "了", "是", "和", "與", "會", "越", "比較", "我", "覺得", "看", "有", "就", "也", "都", "跟", "在", "很", "因為", "所以", "可能", "影響", "物體", "時間"];
  function cloudWords(answers) {
    var seg = window.Intl && Intl.Segmenter ? new Intl.Segmenter("zh-TW", { granularity: "word" }) : null, counts = {};
    answers.forEach(function (a) {
      var words = seg ? Array.from(seg.segment(a)).filter(function (x) { return x.isWordLike; }).map(function (x) { return x.segment; }) : a.split(/[\s，,。、；;]+/);
      var seen = {};
      words.forEach(function (w) {
        w = w.trim(); if (!w || STOP.indexOf(w) >= 0 || seen[w]) return;
        if (w.length < 2 && !/[一-鿿]/.test(w)) return;
        seen[w] = 1; counts[w] = (counts[w] || 0) + 1;
      });
    });
    return Object.keys(counts).map(function (k) { return { text: k, weight: counts[k] }; }).sort(function (a, b) { return b.weight - a.weight; }).slice(0, 30);
  }

  XA.quizInsight = function () {
    var st = XA.quizStats(), q = state.session && state.session.quiz;
    if (!st || !st.total) return "還沒有人作答。";
    if (q.type === "open") {
      var w = st.words.slice(0, 3).map(function (x) { return "「" + x.text + "」"; }).join("、");
      return "共 " + st.total + " 則回應，最常出現的是 " + w + "。" + (st.words.some(function (x) { return /重/.test(x.text); }) ? "有同學提到重量，這是常見迷思，可以接著用實驗來檢驗。" : "");
    }
    var parts = ["答對率 " + st.rate + "%。"];
    if (st.topWrong) {
      var pct = Math.round(st.counts[st.topWrong.label] / st.total * 100);
      parts.push((pct >= 50 ? "超過一半" : "有 " + pct + "%") + "的同學選 " + st.topWrong.label + "。");
      if (st.topWrong.misconception) parts.push("可能是" + st.topWrong.misconception + "。");
    }
    if (q.example && XA.likesExamples()) parts.push("我們用生活例子想想看：" + q.example);
    return parts.join("");
  };

  /* ---------- views ---------- */
  var live = null;
  function updateLive() {
    if (!live) return;
    var n = Object.keys(state.responses).length;
    live.count.textContent = "已作答 " + n + (live.expected ? " / " + live.expected : "");
    live.bar.style.width = Math.min(100, live.expected ? n / live.expected * 100 : n * 3) + "%";
    if (state.showResults) renderResults(live.results);
  }

  function stage() {
    var s = state.session;
    if (!s) return h("div", { class: "panel" }, h("h3", null, "投影區"), h("p", { class: "xa-caption" }, "按「派發題目」後，QR Code 會出現在這裡，學生用手機或平板掃描作答。"));
    var q = s.quiz, url = XA.quizStudentUrl();
    var bar = h("span", { style: { width: "0%" } }), count = h("p", { class: "xa-caption", style: { marginTop: "8px" } }, "已作答 0");
    var expected = XA.store.get("classSize", 30);
    var results = h("div", { class: "mt" });
    live = { bar: bar, count: count, results: results, expected: expected };
    var card = h("section", { class: "xa xa-card xa-quiz" },
      h("div", { class: "xa-stack" },
        h("div", { class: "xa-row" }, h("span", { class: "xa-badge xa-badge-brand" }, ({ single: "單選題", multi: "多選題", open: "觀念思考題" })[q.type]), h("span", { class: "xa-code" }, s.code),
          s.topic ? h("span", { class: "xa-badge xa-badge-neutral" }, "跨裝置") : h("span", { class: "xa-badge xa-badge-neutral", title: "到設定開啟跨裝置作答" }, "僅本機分頁")),
        h("p", { class: "xa-question" }, q.stem),
        q.type !== "open" ? h("ol", { style: { margin: 0, paddingLeft: "0", listStyle: "none", font: "500 18px/30px var(--font-sans)" } }, q.options.map(function (o) { return h("li", null, o.label + ". " + o.text); })) : null,
        h("div", null, h("div", { class: "xa-progress", role: "progressbar", "aria-label": "作答進度" }, bar), count)),
      h("a", { class: "xa-qr", href: url, target: "_blank", rel: "noopener", title: "也可以點這裡開學生作答頁" }, qrSvg(url)));
    var stageEl = h("div", { class: "stage", id: "quiz-stage" },
      h("div", { class: "stage-status" }, XA.statusEl()),
      h("button", { class: "iconbtn stage-exit", onclick: function () { stageEl.classList.remove("projecting"); } }, "結束投影 Esc"),
      card, results);
    var tools = h("div", { class: "toolbar" },
      h("button", { class: "xa-btn xa-btn-secondary", onclick: function () { simulate(30); } }, "模擬全班作答（30 人）"),
      h("button", { class: "xa-btn xa-btn-primary", onclick: function () { state.showResults = true; renderResults(results); XA.say(XA.quizInsight()); } }, "結束並統計"),
      h("button", { class: "xa-btn xa-btn-secondary", onclick: function () { stageEl.classList.add("projecting"); } }, "全螢幕投影"),
      h("label", { class: "check", style: { margin: 0 } }, "全班", h("input", { class: "input", type: "number", min: 1, max: 60, value: expected, style: { width: "64px" }, onchange: function (e) { XA.store.set("classSize", +e.target.value || 30); live.expected = +e.target.value || 30; updateLive(); } }), "人"));
    setTimeout(function () { updateLive(); if (state.showResults) renderResults(results); }, 0);
    return h("div", null, tools, stageEl);
  }

  function renderResults(box) {
    XA.clear(box);
    var st = XA.quizStats(), q = state.session.quiz;
    if (!st.total) { box.appendChild(h("p", { class: "xa-caption" }, "還沒有人作答。可以先按「模擬全班作答」預演。")); return; }
    if (q.type === "open") {
      var max = st.words.length ? st.words[0].weight : 1, order = [];
      st.words.forEach(function (w, i) { if (i % 2) order.push(w); else order.unshift(w); });
      box.appendChild(h("section", { class: "xa xa-card" }, h("p", { class: "xa-eyebrow" }, q.stem + " · " + st.total + " 則回應"),
        h("div", { class: "xa-cloud", role: "list" }, order.map(function (w) { return h("span", { role: "listitem", class: "w" + Math.max(1, Math.ceil(w.weight / max * 5)), title: w.weight + " 則" }, w.text); })),
        h("div", { class: "xa-insight" }, h("b", null, "小安的觀察："), state.insight || XA.quizInsight())));
    } else {
      box.appendChild(h("section", { class: "xa xa-card" },
        h("p", { class: "xa-eyebrow" }, (q.topic || "本題") + (q.type === "multi" ? " · 多選：完全答對才算對" : "")),
        h("div", { class: "xa-stats-head" }, h("span", { class: "xa-stat" }, st.rate + "%"), h("span", { class: "xa-caption" }, "答對率 · 共 " + st.total + " 人作答")),
        h("ol", { class: "xa-bars" }, q.options.map(function (o) {
          var pc = Math.round(st.counts[o.label] / st.total * 100);
          var mis = st.topWrong && st.topWrong.label === o.label;
          var kind = o.correct ? "correct" : (mis ? "misconception" : "");
          return h("li", { class: "xa-bar" + (kind ? " xa-bar-" + kind : "") },
            h("span", { class: "xa-bar-key" }, o.label),
            h("span", { class: "xa-bar-track" }, h("span", { class: "xa-bar-fill", style: { width: Math.max(pc, 2) + "%", opacity: kind ? 0.22 : 0.35 } }),
              h("span", { class: "xa-bar-text" }, o.text,
                o.correct ? h("span", { class: "xa-bar-tag", style: { color: "var(--correct)" } }, "  ✓ 正解") : null,
                mis ? h("span", { class: "xa-bar-tag", style: { color: "var(--misconception)" } }, "  ! 迷思") : null)),
            h("span", { class: "xa-bar-pct" }, pc + "%"));
        })),
        h("div", { class: "xa-insight" }, h("b", null, "小安的觀察："), state.insight || XA.quizInsight())));
    }
    box.appendChild(h("div", { class: "toolbar mt" },
      h("button", { class: "xa-btn xa-btn-secondary", onclick: deepInsight }, "請小安深入分析（AI）"),
      h("button", { class: "xa-btn xa-btn-secondary", onclick: function () { XA.go("board"); XA.boardFromQuiz(q); } }, "到黑板講解"),
      h("button", { class: "xa-btn xa-btn-quiet", onclick: function () { showR(st, q); } }, "R 統計程式碼"),
      h("button", { class: "xa-btn xa-btn-quiet", onclick: exportCsv }, "下載 CSV")));
  }

  function deepInsight() {
    var st = XA.quizStats(), q = state.session.quiz;
    var data = q.type === "open"
      ? "開放題：" + q.stem + "\n學生回應：\n" + Object.keys(state.responses).map(function (k) { return "- " + state.responses[k]; }).join("\n")
      : "題目：" + q.stem + "\n" + q.options.map(function (o) { return o.label + ". " + o.text + (o.correct ? "（正解）" : "") + "：" + st.counts[o.label] + " 人"; }).join("\n") + "\n共 " + st.total + " 人，答對率 " + st.rate + "%。";
    XA.askOrExplain(data + "\n\n請用 3–4 句話分析全班的迷思概念：最主要的錯誤想法、可能的來源（例如受傳統背誦影響）、一個生活實例，以及下一步老師可以怎麼引導。", { maxTokens: 600 })
      .then(function (t) { if (t) { state.insight = t; renderResults(live.results); XA.say(t); } });
  }

  function exportCsv() {
    var rows = [["device", "answer"]].concat(Object.keys(state.responses).map(function (k) { return [k, [].concat(state.responses[k]).join("|")]; }));
    var csv = rows.map(function (r) { return r.map(function (c) { return '"' + String(c).replace(/"/g, '""') + '"'; }).join(","); }).join("\n");
    XA.download("xiaoan-" + state.session.code + ".csv", new Blob(["﻿" + csv], { type: "text/csv" }));
  }

  function showR(st, q) {
    var code = q.type === "open"
      ? "# 文字雲（R）\ninstall.packages(c(\"wordcloud2\"))\nlibrary(wordcloud2)\nfreq <- data.frame(word = c(" + st.words.map(function (w) { return JSON.stringify(w.text); }).join(", ") + "),\n                   freq = c(" + st.words.map(function (w) { return w.weight; }).join(", ") + "))\nwordcloud2(freq, fontFamily = \"Noto Sans TC\", color = \"#0d7a6a\")"
      : "# 答題統計（R）\ncounts <- c(" + q.options.map(function (o) { return o.label + " = " + st.counts[o.label]; }).join(", ") + ")\nprop <- round(prop.table(counts) * 100)\nprint(prop)\ncols <- c(" + q.options.map(function (o) { return o.correct ? "\"#2a66ad\"" : (st.topWrong && st.topWrong.label === o.label ? "\"#b54814\"" : "\"#8c958f\""); }).join(", ") + ")\nbarplot(prop, col = cols, ylab = \"%\", main = \"答對率 " + st.rate + "%\")";
    var scrim = h("div", { class: "scrim", onclick: function (e) { if (e.target === scrim) scrim.remove(); } },
      h("div", { class: "panel", style: { maxWidth: "640px", width: "100%" } }, h("h3", null, "用 R 重現這份統計"),
        h("pre", { class: "code" }, code),
        h("div", { class: "toolbar" }, h("button", { class: "xa-btn xa-btn-primary", onclick: function () { navigator.clipboard && navigator.clipboard.writeText(code); XA.toast("已複製 R 程式碼"); } }, "複製"),
          h("button", { class: "xa-btn xa-btn-secondary", onclick: function () { scrim.remove(); } }, "關閉"))));
    document.body.appendChild(scrim);
  }

  /* ---------- 類題 ---------- */
  function aiVariant() {
    var d = state.draft;
    if (d.id === "fall" || /自由落|落下/.test(d.stem)) { state.draft = XA.fallVariant(); XA.render(); XA.say("出了一題類題：" + state.draft.stem); return; }
    XA.askOrExplain("請根據這題出一題觀念相同、數字或情境不同的類題，只回傳 JSON：{\"stem\":\"…\",\"options\":[{\"label\":\"A\",\"text\":\"…\",\"correct\":true|false,\"misconception\":\"選這個的迷思或空字串\"}],\"example\":\"一句生活實例\"}。題型：" + d.type + "。原題：" + d.stem + "\n選項：" + d.options.map(function (o) { return o.label + ". " + o.text + (o.correct ? "（正解）" : ""); }).join("；"), { maxTokens: 800 })
      .then(function (t) {
        if (!t) return;
        try {
          var j = JSON.parse(t.slice(t.indexOf("{"), t.lastIndexOf("}") + 1));
          state.draft = { id: "custom", type: d.type, topic: d.topic, stem: j.stem, options: (j.options || []).map(function (o, i) { return { label: "ABCDEF"[i], text: String(o.text), correct: !!o.correct, misconception: o.misconception || "" }; }), example: j.example || "" };
          XA.render(); XA.say("類題出好了，請老師先看過再派發。");
        } catch (e) { XA.say("類題格式解析失敗，請再試一次。"); }
      });
  }

  /* free-fall variant with distractors built from real misconceptions; answer self-checked */
  XA.fallVariant = function () {
    var H = [5, 10, 20, 45, 80][Math.floor(Math.random() * 5)], g = 9.8, t = Math.sqrt(2 * H / g);
    var wrongDiv5 = H / 5, wrongNoHalf = Math.sqrt(H / g);
    var opts = XA.shuffle([
      { text: "約 " + XA.round(t, 1) + " 秒", correct: true },
      { text: XA.round(wrongDiv5, 1) + " 秒", misconception: "把公式背成「時間＝高度÷5」，沒有用到 H = ½gt²" },
      { text: "約 " + XA.round(wrongNoHalf, 1) + " 秒", misconception: "代入時漏掉 ½，算成 H = gt²" },
      { text: "要看物體多重", misconception: "以為重的東西掉得比較快" }]);
    // self-check: the correct option must satisfy H = ½ g t² within rounding
    var ok = Math.abs(0.5 * g * Math.pow(XA.round(t, 1), 2) - H) / H < 0.06;
    opts.forEach(function (o, i) { o.label = "ABCD"[i]; });
    return { id: "fall-v", type: "single", topic: "自由落體", stem: "一個物體從 " + H + " 公尺高處自由落下（g = 9.8 m/s²），大約幾秒落地？", options: opts,
      example: "就像從 " + Math.max(2, Math.round(H / 3)) + " 樓高的地方放開一顆球。", selfCheck: ok, H: H, t: t };
  };

  XA.views.quiz = function (root) {
    root.appendChild(h("h2", { class: "view-title" }, "課堂即時互動"));
    root.appendChild(h("p", { class: "view-sub" }, "出題、派發 QR Code、即時收回答案，再由小安統計答對率並分析迷思。"));
    root.appendChild(h("div", { class: "grid2", style: { gridTemplateColumns: "minmax(0,1fr) minmax(0,1.5fr)" } }, editor(), stage()));
  };
})();
