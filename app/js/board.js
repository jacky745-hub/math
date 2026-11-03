/* 小安 Xiao-An — 動態黑板推導與幾何繪圖: step-by-step derivations, practice-question generation, function graphs. */
(function () {
  var XA = window.XA, h = XA.h, s = XA.s, r = XA.round;

  function fmt(x) { var v = r(x, 2); return (v < 0 ? "−" + Math.abs(v) : String(v)); }
  function signed(x) { return x < 0 ? " − " + fmt(Math.abs(x)) : " + " + fmt(x); }

  var TEMPLATES = {
    fall: {
      name: "自由落體：由高度求時間",
      params: [{ k: "H", label: "高度 H（公尺）", v: 20 }, { k: "g", label: "重力加速度 g（m/s²）", v: 9.8 }],
      steps: function (p) {
        var t2 = 2 * p.H / p.g, t = Math.sqrt(t2);
        return [
          { expr: "H = ½ g t²", note: "物體從靜止落下，位移公式", say: "物體從靜止開始落下，所以用 H 等於二分之一 g t 平方。" },
          { expr: fmt(p.H) + " = ½ × " + fmt(p.g) + " × t²", note: "代入 H = " + fmt(p.H) + "、g = " + fmt(p.g), say: "把高度 " + fmt(p.H) + " 和 g 等於 " + fmt(p.g) + " 代進去。" },
          { expr: "t² = 2H ÷ g = " + fmt(2 * p.H) + " ÷ " + fmt(p.g), note: "兩邊同乘 2，再除以 g", say: "兩邊乘以 2，再除以 g。" },
          { expr: "t² ≈ " + fmt(t2), say: "t 平方大約是 " + fmt(t2) + "。" },
          { expr: "t ≈ " + fmt(t) + " 秒", answer: true, say: "開根號，大約 " + fmt(t) + " 秒落地。" }];
      },
      check: function (p) { var t = Math.sqrt(2 * p.H / p.g); return Math.abs(0.5 * p.g * t * t - p.H) < 1e-9; }
    },
    vertex: {
      name: "二次函數：配方求頂點",
      params: [{ k: "a", label: "a", v: 1 }, { k: "b", label: "b", v: -4 }, { k: "c", label: "c", v: 3 }],
      steps: function (p) {
        if (!p.a) return [{ expr: "a 不能是 0", note: "a = 0 時不是二次函數" }];
        var hh = -p.b / (2 * p.a), k = p.c - p.b * p.b / (4 * p.a);
        return [
          { expr: "y = " + fmt(p.a) + "x²" + signed(p.b) + "x" + signed(p.c), note: "原式", say: "先寫下原式。" },
          { expr: "y = " + fmt(p.a) + "(x²" + signed(p.b / p.a) + "x)" + signed(p.c), note: "提出 a", say: "把 a 提出來。" },
          { expr: "y = " + fmt(p.a) + "(x" + signed(-hh) + ")²" + signed(k), note: "配方：加減 (b/2a)²", say: "配方，加上再減去一半係數的平方。" },
          { expr: "頂點 (" + fmt(hh) + ", " + fmt(k) + ")", answer: true, note: "對稱軸 x = " + fmt(hh) + (p.a > 0 ? "，開口向上，最低點" : "，開口向下，最高點"), say: "所以頂點是 " + fmt(hh) + " 逗號 " + fmt(k) + "。" }];
      },
      check: function (p) { var hh = -p.b / (2 * p.a); var k = p.c - p.b * p.b / (4 * p.a); return Math.abs(p.a * hh * hh + p.b * hh + p.c - k) < 1e-9; }
    },
    custom: { name: "自訂推導（一行一步）", params: [], steps: null }
  };

  var B = { tpl: "fall", p: { H: 20, g: 9.8 }, cur: 0, custom: "v = v₀ + at\n= 0 + 9.8 × 2\n= 19.6 m/s", practice: null, reveal: false };
  XA.board = B;

  function steps() {
    if (B.tpl === "custom") return B.custom.split("\n").filter(function (x) { return x.trim(); }).map(function (x, i, a) { return { expr: x.trim(), answer: i === a.length - 1 && a.length > 1 }; });
    return TEMPLATES[B.tpl].steps(B.p);
  }
  XA.boardSteps = steps;

  XA.boardStep = function (dir) {
    var st = steps();
    B.cur = Math.max(0, Math.min(st.length - 1, B.cur + dir));
    var cur = st[B.cur];
    XA.renderBoardOnly && XA.renderBoardOnly();
    if (cur) XA.speak(cur.say || cur.expr);
    return cur;
  };

  XA.boardFromQuiz = function (q) {
    if (/自由落|落下/.test(q.stem)) {
      var m = q.stem.match(/(\d+(?:\.\d+)?)\s*公尺/);
      B.tpl = "fall"; B.p = { H: m ? +m[1] : 20, g: 9.8 };
    } else if (/y\s*=/.test(q.stem)) {
      var co = parseQuadratic(q.stem.slice(q.stem.indexOf("=") + 1));
      if (co) { B.tpl = "vertex"; B.p = co; }
    } else { B.tpl = "custom"; B.custom = q.stem; }
    B.cur = 0; B.practice = null;
    XA.render();
    XA.say("我們一步一步來推導。按右方向鍵或說「下一步」。");
  };

  /* parse "x² − 4x + 3" → {a,b,c} */
  function parseQuadratic(str) {
    var t = str.replace(/[−–]/g, "-").replace(/²/g, "^2").replace(/\s+/g, "").replace(/[，。？?].*$/, "").replace(/的.*$/, "");
    var m = t.match(/^([+-]?\d*\.?\d*)x\^2(?:([+-]\d*\.?\d*)x)?([+-]\d+\.?\d*)?$/);
    if (!m) return null;
    function num(x, d) { if (x === undefined) return d; if (x === "" || x === "+") return 1; if (x === "-") return -1; return +x; }
    return { a: num(m[1], 1), b: m[2] === undefined ? 0 : num(m[2], 1), c: m[3] === undefined ? 0 : +m[3] };
  }
  XA.parseQuadratic = parseQuadratic;

  function practice() {
    if (B.tpl === "fall") {
      var v = XA.fallVariant();
      B.practice = { q: v.stem, a: "t = √(2H ÷ g) = √(" + 2 * v.H + " ÷ 9.8) ≈ " + fmt(v.t) + " 秒", quiz: v, ok: v.selfCheck };
    } else if (B.tpl === "vertex") {
      var a = [1, 2, -1][Math.floor(Math.random() * 3)], hh = Math.floor(Math.random() * 7) - 3, k = Math.floor(Math.random() * 9) - 4;
      var b = -2 * a * hh, c = a * hh * hh + k;
      var ok = TEMPLATES.vertex.check({ a: a, b: b, c: c });
      B.practice = { q: "求 y = " + fmt(a) + "x²" + signed(b) + "x" + signed(c) + " 的頂點座標。", a: "頂點 (" + hh + ", " + k + ")", ok: ok,
        quiz: { id: "vertex-v", type: "single", topic: "二次函數", stem: "二次函數 y = " + fmt(a) + "x²" + signed(b) + "x" + signed(c) + " 的頂點座標是？",
          options: XA.shuffle([{ text: "(" + hh + ", " + k + ")", correct: true }, { text: "(" + -hh + ", " + k + ")", misconception: "對稱軸 x = −b/2a 的符號弄反" }, { text: "(" + hh + ", " + c + ")", misconception: "找到對稱軸後忘了代回求 y，直接拿常數項" }, { text: "(" + (hh + 1) + ", " + (k - 1) + ")" }]).map(function (o, i) { o.label = "ABCD"[i]; return o; }) } };
    } else {
      XA.askOrExplain("根據這段推導出一題類題，回傳兩行：第一行「題目：…」，第二行「答案：…」。推導：\n" + B.custom, { maxTokens: 400 }).then(function (t) {
        if (!t) return;
        var q = (t.match(/題目[:：](.*)/) || [])[1], a = (t.match(/答案[:：](.*)/) || [])[1];
        B.practice = { q: (q || t).trim(), a: (a || "").trim(), ok: null }; B.reveal = false; XA.render();
      });
      return;
    }
    B.reveal = false; XA.render();
    XA.say("類題來了：" + B.practice.q + " 大家先自己算算看。");
  }

  /* ---------- board view ---------- */
  var boardBox = null;
  function boardEl() {
    var st = steps();
    B.cur = Math.min(B.cur, st.length - 1);
    var stageEl = h("div", { class: "stage", id: "board-stage" },
      h("div", { class: "stage-status" }, XA.statusEl()),
      h("button", { class: "iconbtn stage-exit", onclick: function () { stageEl.classList.remove("projecting"); } }, "結束投影 Esc"),
      h("section", { class: "xa xa-board", "aria-label": "黑板推導" },
        h("p", { class: "xa-board-title" }, TEMPLATES[B.tpl].name),
        h("ol", { class: "xa-steps" }, st.map(function (x, i) {
          if (i > B.cur) return null;
          var cls = i < B.cur ? "done" : (x.answer ? "answer xa-step-current" : "current");
          return h("li", { class: "xa-step xa-step-" + cls, "aria-current": i === B.cur ? "step" : null },
            h("span", { class: "xa-step-expr" }, x.expr), x.note ? h("span", { class: "xa-step-note" }, x.note) : null);
        })),
        B.practice ? h("div", { class: "board-answer" }, "類題：" + B.practice.q, B.reveal ? h("div", null, "答案：" + B.practice.a, B.practice.ok === true ? h("span", { class: "xa-step-note", style: { display: "block" } }, "（小安已自我驗算：代回公式成立）") : null) : null) : null));
    return stageEl;
  }
  XA.renderBoardOnly = function () { if (boardBox && boardBox.isConnected) { XA.clear(boardBox).appendChild(boardEl()); } };

  XA.views.board = function (root) {
    root.appendChild(h("h2", { class: "view-title" }, "黑板推導"));
    root.appendChild(h("p", { class: "view-sub" }, "小安在電子黑板上一步一步寫出推導，邊寫邊說；可以現場出類題。鍵盤 ← → 換步驟。"));
    var t = TEMPLATES[B.tpl];
    var params = h("div", { class: "row" }, t.params.map(function (pp) {
      return h("div", { class: "field" }, pp.label, h("input", { type: "number", step: "any", value: B.p[pp.k] != null ? B.p[pp.k] : pp.v, onchange: function (e) { B.p[pp.k] = +e.target.value; B.cur = 0; XA.renderBoardOnly(); } }));
    }));
    var ctl = h("div", { class: "panel" },
      h("h3", null, "推導設定"),
      h("div", { class: "field" }, "主題", h("select", { onchange: function (e) {
        B.tpl = e.target.value; B.cur = 0; B.practice = null; B.p = {};
        TEMPLATES[B.tpl].params.forEach(function (pp) { B.p[pp.k] = pp.v; }); XA.render();
      } }, Object.keys(TEMPLATES).map(function (k) { return h("option", { value: k, selected: k === B.tpl }, TEMPLATES[k].name); }))),
      B.tpl === "custom" ? h("div", { class: "field" }, "每行一個步驟（最後一行會圈起來當答案）", h("textarea", { rows: 5, oninput: function (e) { B.custom = e.target.value; XA.renderBoardOnly(); } }, B.custom)) : params,
      h("div", { class: "toolbar" },
        h("button", { class: "xa-btn xa-btn-secondary", onclick: function () { XA.boardStep(-1); } }, "← 上一步"),
        h("button", { class: "xa-btn xa-btn-primary", onclick: function () { XA.boardStep(1); } }, "下一步 →"),
        h("button", { class: "xa-btn xa-btn-quiet", onclick: function () { B.cur = steps().length - 1; XA.renderBoardOnly(); } }, "全部顯示")),
      h("h3", { class: "mt" }, "動態類題"),
      h("div", { class: "toolbar" },
        h("button", { class: "xa-btn xa-btn-secondary", onclick: practice }, "出一題類題"),
        B.practice ? h("button", { class: "xa-btn xa-btn-secondary", onclick: function () { B.reveal = !B.reveal; XA.renderBoardOnly(); if (B.reveal) XA.speak("答案是 " + B.practice.a); } }, B.reveal ? "隱藏答案" : "揭曉答案") : null,
        B.practice && B.practice.quiz ? h("button", { class: "xa-btn xa-btn-quiet", onclick: function () { XA.quizDispatch(B.practice.quiz); } }, "派發成 QR 測驗") : null),
      h("div", { class: "toolbar mt" },
        h("button", { class: "xa-btn xa-btn-secondary", onclick: function () { document.getElementById("board-stage").classList.add("projecting"); } }, "全螢幕投影"),
        B.tpl === "vertex" ? h("button", { class: "xa-btn xa-btn-quiet", onclick: function () { XA.graph.a = B.p.a; XA.graph.b = B.p.b; XA.graph.c = B.p.c; XA.graph.expr = ""; XA.go("graph"); } }, "畫出這個函數") : null));
    boardBox = h("div", null, boardEl());
    root.appendChild(h("div", { class: "grid2", style: { gridTemplateColumns: "minmax(0,1fr) minmax(0,1.6fr)" } }, ctl, boardBox));
  };

  /* ---------- function graph ---------- */
  var G = (XA.graph = { a: 1, b: -4, c: 3, expr: "", showFocus: true });

  function compile(expr) {
    var e = expr.replace(/\s+/g, "").replace(/[−–]/g, "-").replace(/²/g, "^2").replace(/^y=/, "");
    if (!/^[0-9x+\-*/^().a-z]*$/.test(e)) return null;
    var words = e.match(/[a-z]+/g) || [];
    var allowed = ["x", "sin", "cos", "tan", "sqrt", "abs", "log", "exp", "pi"];
    if (words.some(function (w) { return allowed.indexOf(w) < 0; })) return null;
    e = e.replace(/(\d)(x|\()/g, "$1*$2").replace(/\)(x|\d|\()/g, ")*$1").replace(/x\(/g, "x*(").replace(/\^/g, "**")
      .replace(/\b(sin|cos|tan|sqrt|abs|log|exp)\b/g, "Math.$1").replace(/\bpi\b/g, "Math.PI");
    try { var f = new Function("x", "return " + e + ";"); f(1); return f; } catch (err) { return null; }
  }

  function plot() {
    var W = 720, Hh = 480, quad = !G.expr, f, vx = 0, vy = 0;
    if (quad) {
      if (!G.a) return h("p", { class: "scene-empty" }, "a 不能是 0。");
      vx = -G.b / (2 * G.a); vy = G.c - G.b * G.b / (4 * G.a);
      f = function (x) { return G.a * x * x + G.b * x + G.c; };
    } else {
      f = compile(G.expr);
      if (!f) return h("p", { class: "scene-empty" }, "看不懂這個式子。可用 x、+ − × ÷、^、sin、cos、sqrt，例如 y = 0.5x^2 - 3。");
    }
    var span = quad ? Math.max(4, Math.abs(1 / G.a) * 4 + 2) : 10;
    var x0 = (quad ? vx : 0) - span, x1 = (quad ? vx : 0) + span;
    var ys = []; for (var i = 0; i <= 200; i++) { var y = f(x0 + (x1 - x0) * i / 200); if (isFinite(y)) ys.push(y); }
    var y0 = quad ? Math.min(vy, 0) - span * 0.3 : Math.max(-10, Math.min.apply(null, ys)), y1 = quad ? Math.max(vy, 0) + span * 1.1 : Math.min(10, Math.max.apply(null, ys));
    if (quad && G.a < 0) { y0 = Math.min(vy, 0) - span * 1.1; y1 = Math.max(vy, 0) + span * 0.3; }
    if (y1 - y0 < 1) { y0 -= 1; y1 += 1; }
    var pad = 40;
    function X(x) { return pad + (x - x0) / (x1 - x0) * (W - 2 * pad); }
    function Y(y) { return Hh - pad - (y - y0) / (y1 - y0) * (Hh - 2 * pad); }
    var kids = [], step = Math.pow(10, Math.floor(Math.log10((x1 - x0) / 4))) || 1;
    for (var gx = Math.ceil(x0 / step) * step; gx <= x1; gx += step) { kids.push(s("line", { class: "grid", x1: X(gx), x2: X(gx), y1: pad, y2: Hh - pad })); if (Math.abs(gx) > 1e-9) kids.push(s("text", { class: "tick", x: X(gx), y: Math.min(Hh - pad + 16, Math.max(pad + 12, Y(0) + 16)), "text-anchor": "middle" }, r(gx, 2))); }
    var ystep = Math.pow(10, Math.floor(Math.log10((y1 - y0) / 4))) || 1;
    for (var gy = Math.ceil(y0 / ystep) * ystep; gy <= y1; gy += ystep) { kids.push(s("line", { class: "grid", y1: Y(gy), y2: Y(gy), x1: pad, x2: W - pad })); if (Math.abs(gy) > 1e-9) kids.push(s("text", { class: "tick", y: Y(gy) + 4, x: Math.min(W - pad - 4, Math.max(pad + 4, X(0) - 6)), "text-anchor": "end" }, r(gy, 2))); }
    if (y0 < 0 && y1 > 0) kids.push(s("line", { class: "axis", x1: pad, x2: W - pad, y1: Y(0), y2: Y(0) }));
    if (x0 < 0 && x1 > 0) kids.push(s("line", { class: "axis", y1: pad, y2: Hh - pad, x1: X(0), x2: X(0) }));
    var d = "", pen = false;
    for (var j = 0; j <= 400; j++) {
      var xx = x0 + (x1 - x0) * j / 400, yy = f(xx);
      if (!isFinite(yy) || yy < y0 - (y1 - y0) || yy > y1 + (y1 - y0)) { pen = false; continue; }
      d += (pen ? "L" : "M") + r(X(xx), 1) + " " + r(Y(yy), 1); pen = true;
    }
    var clip = s("clipPath", { id: "plotclip" }, s("rect", { x: pad, y: pad, width: W - 2 * pad, height: Hh - 2 * pad }));
    var curve = s("path", { class: "curve", d: d, "clip-path": "url(#plotclip)" });
    var marks = [];
    if (quad) {
      var p = 1 / (4 * G.a);
      marks.push(s("line", { class: "guide", x1: X(vx), x2: X(vx), y1: pad, y2: Hh - pad }));
      marks.push(s("circle", { class: "mark", cx: X(vx), cy: Y(vy), r: 6 }));
      marks.push(s("text", { class: "lbl", x: X(vx) + 12, y: Y(vy) + (G.a > 0 ? 24 : -12) }, "頂點 (" + fmt(vx) + ", " + fmt(vy) + ")"));
      if (G.showFocus) {
        marks.push(s("circle", { class: "mark", cx: X(vx), cy: Y(vy + p), r: 5 }));
        marks.push(s("text", { class: "lbl", x: X(vx) - 12, y: Y(vy + p) + 6, "text-anchor": "end" }, "焦點 (" + fmt(vx) + ", " + fmt(vy + p) + ")"));
        if (Y(vy - p) > pad && Y(vy - p) < Hh - pad) {
          marks.push(s("line", { class: "guide", x1: pad, x2: W - pad, y1: Y(vy - p), y2: Y(vy - p) }));
          marks.push(s("text", { class: "lbl", x: W - pad - 4, y: Y(vy - p) - 8, "text-anchor": "end" }, "準線 y = " + fmt(vy - p)));
        }
      }
    }
    return s("svg", { class: "board-graph", viewBox: "0 0 " + W + " " + Hh, role: "img", "aria-label": quad ? "y = " + G.a + "x² + " + G.b + "x + " + G.c + " 的圖形，頂點 (" + fmt(vx) + ", " + fmt(vy) + ")" : "y = " + G.expr + " 的圖形" },
      s("defs", null, clip), kids, curve, marks);
  }

  XA.views.graph = function (root) {
    root.appendChild(h("h2", { class: "view-title" }, "函數繪圖"));
    root.appendChild(h("p", { class: "view-sub" }, "即時畫出函數圖形；二次函數會自動標出頂點、焦點、準線與對稱軸。"));
    var box = h("div", { class: "xa-board", style: { padding: "16px" } });
    function draw() { XA.clear(box).appendChild(plot()); }
    function num(k, label) {
      var out = h("output", null, G[k]);
      return h("div", { class: "field" }, h("span", null, label + " = ", out),
        h("input", { type: "range", min: -6, max: 6, step: 0.5, value: G[k], oninput: function (e) { G[k] = +e.target.value; out.textContent = G[k]; G.expr = ""; exprIn.value = ""; draw(); } }));
    }
    var exprIn = h("input", { value: G.expr, placeholder: "例如 y = sin(x) 或 0.5x^2 - 3", onchange: function (e) {
      var q = parseQuadratic(e.target.value.replace(/^\s*y\s*=/, ""));
      if (q) { G.a = q.a; G.b = q.b; G.c = q.c; G.expr = ""; XA.render(); return; }
      G.expr = e.target.value.replace(/^\s*y\s*=/, ""); draw();
    } });
    var ctl = h("div", { class: "panel" }, h("h3", null, "y = ax² + bx + c"), num("a", "a"), num("b", "b"), num("c", "c"),
      h("label", { class: "check" }, h("input", { type: "checkbox", checked: G.showFocus, onchange: function (e) { G.showFocus = e.target.checked; draw(); } }), "標示焦點與準線"),
      h("h3", { class: "mt" }, "或輸入任意函數"), h("div", { class: "field" }, exprIn),
      h("div", { class: "toolbar" },
        h("button", { class: "xa-btn xa-btn-secondary", onclick: function () {
          if (G.expr) { XA.say("這是 y = " + G.expr + " 的圖形。"); return; }
          var vx = -G.b / (2 * G.a), vy = G.c - G.b * G.b / (4 * G.a);
          XA.say("這條拋物線開口向" + (G.a > 0 ? "上" : "下") + "，頂點在 " + fmt(vx) + " 逗號 " + fmt(vy) + "，焦點在頂點" + (G.a > 0 ? "上方 " : "下方 ") + fmt(Math.abs(1 / (4 * G.a))) + " 的地方。");
        } }, "請小安說明"),
        h("button", { class: "xa-btn xa-btn-quiet", onclick: function () {
          var url = "https://www.geogebra.org/calculator?lang=zh-TW";
          XA.openLink("開啟 GeoGebra 計算機", url, "在新分頁開啟 GeoGebra，讓學生自己拖拉參數。網址：" + url);
        } }, "在 GeoGebra 開啟")));
    draw();
    root.appendChild(h("div", { class: "grid2", style: { gridTemplateColumns: "minmax(0,1fr) minmax(0,1.8fr)" } }, ctl, box));
  };
})();
