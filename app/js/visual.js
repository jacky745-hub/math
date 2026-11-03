/* 小安 Xiao-An — 全像投影與 3D/2D 視覺生成: programmatic diagrams + floating info cards (FloatCard). */
(function () {
  var XA = window.XA, h = XA.h, s = XA.s;

  function arteryArt() {
    var cells = [];
    for (var i = 0; i < 9; i++) {
      var a = i / 9 * Math.PI * 2, rr = 30 + (i % 3) * 18;
      cells.push(s("ellipse", { cx: 230 + Math.cos(a) * rr, cy: 230 + Math.sin(a) * rr, rx: 13, ry: 9, fill: "#d64545", stroke: "#8f1f1f", "stroke-width": 2 }));
    }
    var flow = [];
    for (var j = 0; j < 7; j++) flow.push(s("ellipse", { cx: 480 + j * 50, cy: 216 + (j % 3) * 14, rx: 14, ry: 8, fill: "#d64545", stroke: "#8f1f1f", "stroke-width": 2 }));
    flow.push(s("circle", { cx: 530, cy: 250, r: 9, fill: "#f3f0e6", stroke: "#a9b8b0", "stroke-width": 2 }));
    return s("svg", { class: "art", viewBox: "0 0 800 460", role: "img", "aria-label": "動脈血管三層構造剖面與血球流動示意圖" },
      s("circle", { cx: 230, cy: 230, r: 170, fill: "#c9a77c" }),
      s("circle", { cx: 230, cy: 230, r: 138, fill: "#b5534a" }),
      s("g", { stroke: "#9b4038", "stroke-width": 2, opacity: 0.6 }, [0, 1, 2, 3].map(function (k) { return s("circle", { cx: 230, cy: 230, r: 108 + k * 8, fill: "none" }); })),
      s("circle", { cx: 230, cy: 230, r: 100, fill: "#efc6bc" }),
      s("circle", { cx: 230, cy: 230, r: 92, fill: "#5a1414" }),
      cells,
      s("rect", { x: 440, y: 150, width: 340, height: 160, rx: 20, fill: "#c9a77c" }),
      s("rect", { x: 440, y: 168, width: 340, height: 124, fill: "#b5534a" }),
      s("rect", { x: 440, y: 184, width: 340, height: 92, fill: "#efc6bc" }),
      s("rect", { x: 440, y: 190, width: 340, height: 80, fill: "#5a1414" }),
      s("g", { class: "cell-flow" }, flow),
      s("path", { d: "M470 340 h260 l-14 -10 m14 10 l-14 10", stroke: "#f2c94c", "stroke-width": 3, fill: "none" }),
      s("text", { x: 600, y: 372, fill: "#f2c94c", "font-size": 18, "text-anchor": "middle", "font-family": "LXGW WenKai TC, serif" }, "血流方向：離開心臟"));
  }

  function mugArt() {
    return s("svg", { class: "art", viewBox: "0 0 800 460", role: "img", "aria-label": "正方體馬克杯的等角示意圖" },
      s("ellipse", { cx: 380, cy: 400, rx: 200, ry: 26, fill: "#0b1714", opacity: 0.6 }),
      s("polygon", { points: "380,90 540,170 380,250 220,170", fill: "#4cbfac" }),
      s("polygon", { points: "380,110 505,172 380,234 255,172", fill: "#183a33" }),
      s("polygon", { points: "220,170 380,250 380,410 220,330", fill: "#0d7a6a" }),
      s("polygon", { points: "540,170 380,250 380,410 540,330", fill: "#0a5f53" }),
      s("path", { d: "M540 205 C 640 205, 650 315, 540 300", fill: "none", stroke: "#0a5f53", "stroke-width": 26, "stroke-linecap": "round" }),
      s("path", { d: "M540 205 C 640 205, 650 315, 540 300", fill: "none", stroke: "#0d7a6a", "stroke-width": 12, "stroke-linecap": "round" }),
      s("text", { x: 300, y: 300, fill: "#f3f0e6", "font-size": 54, "font-weight": 700, "font-family": "Noto Sans TC, sans-serif", transform: "skewY(26.6) translate(0 -150)" }, "安"));
  }

  var SCENES = {
    artery: { name: "動脈血管三層剖面", art: arteryArt, cards: [
      { eyebrow: "動脈・內膜", title: "讓血液滑順流過", body: "單層內皮細胞，表面平滑，減少血球摩擦。", x: 2, y: 4 },
      { eyebrow: "動脈・中膜", title: "有彈性的肌肉層", body: "平滑肌與彈性纖維，撐住心臟打出的壓力。", x: 2, y: 62 },
      { eyebrow: "動脈・外膜", title: "最外層的保護", body: "結締組織固定血管，也讓血管不易破裂。", x: 56, y: 4 },
      { eyebrow: "血液", title: "紅血球運送氧氣", body: "紅血球形狀像中間凹的圓盤；白血球負責防禦。", x: 56, y: 68 }] },
    mug: { name: "正方體馬克杯", art: mugArt, cards: [
      { eyebrow: "設計理念", title: "方形好收納", body: "正方體可以緊密排在櫃子裡，不浪費空間。", x: 2, y: 6 },
      { eyebrow: "數學連結", title: "容量＝邊長³", body: "內邊長 8 公分，容量約 512 毫升。", x: 2, y: 64 },
      { eyebrow: "人體工學", title: "把手留四指空間", body: "把手內徑約 2.5 公分，握起來不夾手。", x: 66, y: 64 }] }
  };

  var V = { scene: "artery", custom: null, shown: {} };
  XA.visual = V;

  function sanitizeSvg(text) {
    var start = text.indexOf("<svg"), end = text.lastIndexOf("</svg>");
    if (start < 0 || end < 0) return null;
    var doc = new DOMParser().parseFromString(text.slice(start, end + 6), "image/svg+xml");
    var svg = doc.documentElement;
    if (!svg || svg.nodeName !== "svg" || doc.querySelector("parsererror")) return null;
    svg.querySelectorAll("script, foreignObject, iframe, object, embed, image, use, a, style").forEach(function (n) { n.remove(); });
    [svg].concat(Array.from(svg.querySelectorAll("*"))).forEach(function (n) {
      Array.from(n.attributes).forEach(function (a) {
        if (/^on/i.test(a.name) || /href$/i.test(a.name) || /javascript:|url\(\s*['"]?(?!#)/i.test(a.value)) n.removeAttribute(a.name);
      });
    });
    svg.setAttribute("class", "art"); svg.removeAttribute("width"); svg.removeAttribute("height");
    if (!svg.getAttribute("viewBox")) svg.setAttribute("viewBox", "0 0 800 460");
    return document.importNode(svg, true);
  }
  XA.sanitizeSvg = sanitizeSvg;

  function generate(topic) {
    if (!topic) return;
    XA.say("我來畫「" + topic + "」的示意圖。");
    XA.askOrExplain("請畫一張「" + topic + "」的教學示意圖，給國中生看。只輸出：\n1) 一個 <svg viewBox=\"0 0 800 460\"> 元素，深色背景上清楚可見（不要畫背景，不要文字以外的說明，不要 script、image、外部連結），用簡單幾何形狀表現 2D 或等角 3D；\n2) 之後 2 到 4 行字卡，每行格式：卡片｜部位名稱｜一句標題｜一句 30 字內說明。", { maxTokens: 4000 })
      .then(function (t) {
        if (!t) return;
        var svg = sanitizeSvg(t);
        if (!svg) { XA.say("這次的圖不完整，請再試一次。"); return; }
        var cards = (t.slice(t.lastIndexOf("</svg>")).match(/卡片｜[^\n]+/g) || []).slice(0, 4).map(function (line, i) {
          var p = line.split("｜"); return { eyebrow: p[1] || "", title: p[2] || "", body: p[3] || "", x: i % 2 ? 66 : 2, y: i < 2 ? 4 : 64 };
        });
        SCENES.custom = { name: topic, art: function () { return svg.cloneNode(true); }, cards: cards };
        V.scene = "custom"; V.shown = {}; XA.render();
        XA.say("「" + topic + "」畫好了。");
      });
  }
  XA.visualGenerate = generate;

  XA.visualShow = function (key) {
    if (!SCENES[key]) return false;
    V.scene = key; V.shown = {}; XA.go("visual");
    XA.say("投影「" + SCENES[key].name + "」。點右邊的字卡可以逐一浮現說明。");
    return true;
  };

  XA.views.visual = function (root) {
    root.appendChild(h("h2", { class: "view-title" }, "視覺投影"));
    root.appendChild(h("p", { class: "view-sub" }, "投影 2D／3D 示意圖，並在畫面上疊加浮空字卡，補充科學知識或設計理念。"));
    var sc = SCENES[V.scene] || SCENES.artery;
    var cardEls = sc.cards.map(function (c, i) {
      return h("aside", { class: "xa-float" + (V.shown[i] ? "" : " dim"), style: { left: c.x + "%", top: c.y + "%", maxWidth: "28%" }, "aria-hidden": V.shown[i] ? null : "true" },
        h("p", { class: "xa-float-eyebrow" }, c.eyebrow), h("p", { class: "xa-float-title" }, c.title), h("p", { class: "xa-float-body" }, c.body));
    });
    var stageEl = h("div", { class: "stage", id: "visual-stage" },
      h("div", { class: "stage-status" }, XA.statusEl()),
      h("button", { class: "iconbtn stage-exit", onclick: function () { stageEl.classList.remove("projecting"); } }, "結束投影 Esc"),
      h("div", { class: "scene" }, sc.art(), cardEls));
    function toggle(i) {
      V.shown[i] = !V.shown[i];
      cardEls[i].classList.toggle("dim", !V.shown[i]);
      cardEls[i].setAttribute("aria-hidden", V.shown[i] ? "false" : "true");
      if (V.shown[i]) XA.speak(sc.cards[i].eyebrow + "。" + sc.cards[i].title + "。" + sc.cards[i].body);
    }
    var topicIn = h("input", { placeholder: "例如：植物細胞、光的折射、正四面體" });
    var ctl = h("div", { class: "panel" },
      h("h3", null, "選擇畫面"),
      h("div", { class: "toolbar" }, Object.keys(SCENES).map(function (k) {
        return h("button", { class: "xa-btn " + (k === V.scene ? "xa-btn-primary" : "xa-btn-secondary"), onclick: function () { V.scene = k; V.shown = {}; XA.render(); } }, SCENES[k].name);
      })),
      h("h3", { class: "mt" }, "浮空字卡"),
      h("div", { class: "toolbar" }, sc.cards.map(function (c, i) { return h("button", { class: "xa-btn xa-btn-secondary", "aria-pressed": V.shown[i] ? "true" : "false", onclick: function (e) { toggle(i); e.currentTarget.setAttribute("aria-pressed", V.shown[i] ? "true" : "false"); } }, c.eyebrow || ("字卡 " + (i + 1))); })),
      h("div", { class: "toolbar" },
        h("button", { class: "xa-btn xa-btn-quiet", onclick: function () { sc.cards.forEach(function (c, i) { if (!V.shown[i]) toggle(i); }); } }, "全部顯示"),
        h("button", { class: "xa-btn xa-btn-quiet", onclick: function () { sc.cards.forEach(function (c, i) { if (V.shown[i]) toggle(i); }); } }, "全部隱藏")),
      h("h3", { class: "mt" }, "讓小安畫新的示意圖（AI）"),
      h("div", { class: "field" }, topicIn, h("span", { class: "hint" }, "由語言模型產生向量圖（SVG）並自動移除任何程式碼。需要在設定填入 API 金鑰。")),
      h("button", { class: "xa-btn xa-btn-secondary", onclick: function () { generate(topicIn.value.trim()); } }, "產生示意圖"),
      h("div", { class: "toolbar mt" }, h("button", { class: "xa-btn xa-btn-secondary", onclick: function () { stageEl.classList.add("projecting"); } }, "全螢幕投影")));
    root.appendChild(h("div", { class: "grid2", style: { gridTemplateColumns: "minmax(0,1fr) minmax(0,2fr)" } }, ctl, stageEl));
  };
})();
