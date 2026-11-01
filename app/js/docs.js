/* 小安 Xiao-An — Word 文檔即時共編與批改: read questions from .docx, write worked solutions and practice questions back. */
(function () {
  var XA = window.XA, h = XA.h;
  var W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main";

  var D = { name: "", zip: null, xml: null, paras: [], questions: [], extra: [], busy: false };
  XA.docs = D;

  var SAMPLE = "第三單元 自由落體與二次函數 練習卷\n1. 一顆球從 45 公尺高處自由落下（g = 9.8 m/s²），需要幾秒落地？\n(A) 3 秒 (B) 9 秒 (C) 約 3.03 秒 (D) 要看球的質量\n2. 二次函數 y = 2x² − 8x + 5 的頂點坐標為何？\n3. 為什麼羽毛和鐵球在空氣中落下的速度不同，在真空管裡卻同時落地？";

  /* ---------- reading ---------- */
  function paraText(p) { return Array.from(p.getElementsByTagNameNS(W, "t")).map(function (t) { return t.textContent; }).join(""); }

  function loadDocx(file, localPath) {
    D.name = file.name; D.localPath = localPath || null;
    return JSZip.loadAsync(file).then(function (zip) {
      D.zip = zip;
      var f = zip.file("word/document.xml");
      if (!f) throw new Error("這不是 Word（.docx）檔案。");
      return f.async("string");
    }).then(function (text) {
      D.xml = new DOMParser().parseFromString(text, "application/xml");
      var body = D.xml.getElementsByTagNameNS(W, "body")[0];
      D.paras = Array.from(body.getElementsByTagNameNS(W, "p")).map(function (p) { return { node: p, text: paraText(p) }; });
      findQuestions();
    });
  }

  function loadText(text) {
    D.name = "小安_練習卷.docx"; D.zip = null; D.xml = null; D.localPath = null;
    D.paras = text.split(/\r?\n/).map(function (t) { return { node: null, text: t }; });
    findQuestions();
  }

  var Q_START = /^\s*(?:[(（]?\s*(\d{1,2})\s*[)）.．、]|第\s*(\d{1,2})\s*題)/;
  function findQuestions() {
    D.questions = []; D.extra = [];
    var cur = null;
    D.paras.forEach(function (p, i) {
      var m = p.text.match(Q_START);
      if (m && !/^\s*[(（][A-Da-d][)）]/.test(p.text)) {
        cur = { n: +(m[1] || m[2]), text: p.text.replace(Q_START, "").trim(), at: i, end: i, solution: null, check: null, source: null };
        D.questions.push(cur);
      } else if (cur && p.text.trim() && /^\s*[(（]?[A-Da-d][)）.．]/.test(p.text)) {
        cur.text += "\n" + p.text.trim(); cur.end = i;
      } else if (p.text.trim()) { cur = null; }
    });
  }

  /* ---------- solving ---------- */
  function num(x) { return XA.round(x, 2); }
  function solveLocal(q) {
    var t = q.text.replace(/[−–]/g, "-");
    var fall = t.match(/(\d+(?:\.\d+)?)\s*(?:公尺|m).*(?:自由落|落下|落地)|(?:自由落|落下).*?(\d+(?:\.\d+)?)\s*(?:公尺|m)/);
    if (fall) {
      var H = +(fall[1] || fall[2]), gm = t.match(/g\s*=\s*(\d+(?:\.\d+)?)/), g = gm ? +gm[1] : 9.8, tt = Math.sqrt(2 * H / g);
      var opt = (q.text.match(/[(（]([A-D])[)）]\s*約?\s*([\d.]+)\s*秒/g) || []).map(function (s) { var m = s.match(/([A-D])[)）]\s*約?\s*([\d.]+)/); return { l: m[1], v: +m[2] }; })
        .sort(function (a, b) { return Math.abs(a.v - tt) - Math.abs(b.v - tt); })[0];
      var lines = ["【解】物體由靜止落下，H = ½gt²。", "代入 H = " + H + "、g = " + g + "：" + H + " = ½ × " + g + " × t²", "t² = 2H ÷ g = " + num(2 * H) + " ÷ " + g + " ≈ " + num(2 * H / g), "t ≈ " + num(tt) + " 秒" + (opt ? "，答案選 (" + opt.l + ")。" : "。")];
      if (/質量|多重|重量/.test(q.text)) lines.push("（說明：忽略空氣阻力時，落下時間和質量無關。）");
      if (XA.likesExamples()) lines.push("生活實例：從 " + Math.max(2, Math.round(H / 3)) + " 樓高放開一顆球，大約這麼久會落地。");
      var back = 0.5 * g * Math.pow(num(tt), 2);
      return { solution: lines.join("\n"), check: "自我檢查：½ × " + g + " × " + num(tt) + "² ≈ " + num(back) + "，與 H = " + H + " 相符" + (Math.abs(back - H) / H < 0.02 ? " ✓" : "（誤差偏大，請老師確認）"), source: "小安（公式計算）" };
    }
    var qd = t.match(/y\s*=\s*([^，。？?的]+?)\s*(?:的|之)?\s*(?:頂點|最[大小]值)/);
    if (qd) {
      var co = XA.parseQuadratic(qd[1]);
      if (co && co.a) {
        var hh = -co.b / (2 * co.a), k = co.c - co.b * co.b / (4 * co.a);
        var sol = ["【解】y = " + co.a + "x² " + (co.b < 0 ? "− " + -co.b : "+ " + co.b) + "x " + (co.c < 0 ? "− " + -co.c : "+ " + co.c),
          "配方：y = " + co.a + "(x " + (hh < 0 ? "+ " + num(-hh) : "− " + num(hh)) + ")² " + (k < 0 ? "− " + num(-k) : "+ " + num(k)),
          "頂點 (" + num(hh) + ", " + num(k) + ")，對稱軸 x = " + num(hh) + "，開口向" + (co.a > 0 ? "上，有最小值 " : "下，有最大值 ") + num(k) + "。"];
        var yv = co.a * hh * hh + co.b * hh + co.c;
        return { solution: sol.join("\n"), check: "自我檢查：x = " + num(hh) + " 代回原式得 y = " + num(yv) + (Math.abs(yv - k) < 1e-6 ? " ✓" : "（不符，請老師確認）"), source: "小安（配方計算）" };
      }
    }
    return null;
  }

  function solveAll() {
    if (!D.questions.length) { XA.toast("沒有找到題目。題目需要以「1.」「2、」「(3)」或「第 4 題」開頭。"); return; }
    var pending = [];
    D.questions.forEach(function (q) {
      var r = solveLocal(q);
      if (r) Object.assign(q, r); else pending.push(q);
    });
    render();
    if (!pending.length) { XA.say("全部 " + D.questions.length + " 題都解好了，每題都附上自我檢查。請老師看過後再存檔。"); return; }
    if (!XA.hasLLM()) {
      pending.forEach(function (q) { q.solution = "（這題需要語言模型才能作答：請到「設定與記憶」填入 API 金鑰。）"; q.check = null; q.source = "未作答"; });
      render(); XA.say("可以用公式算的題目我已經解好了；其他 " + pending.length + " 題需要連上語言模型。"); return;
    }
    D.busy = true; render();
    var prompt = "請為以下題目寫詳細解題過程，給國中生看。每題用這個格式，題與題之間用一行「===」分隔：\n第N題\n【解】……（逐步推導，說明理由）\n自我檢查：……（把答案代回或用另一種方法驗算，寫出是否一致）\n\n" +
      pending.map(function (q) { return "第" + q.n + "題：" + q.text; }).join("\n\n");
    XA.askOrExplain(prompt, { maxTokens: 3000 }).then(function (t) {
      D.busy = false;
      if (!t) { render(); return; }
      var blocks = t.split(/\n?===\n?/);
      pending.forEach(function (q) {
        var b = blocks.filter(function (x) { return new RegExp("第\\s*" + q.n + "\\s*題").test(x); })[0] || "";
        var sol = b.replace(/^[\s\S]*?(【解】)/, "$1");
        var chk = (sol.match(/自我檢查[:：][\s\S]*$/) || [""])[0];
        q.solution = sol.replace(/自我檢查[:：][\s\S]*$/, "").trim() || "（這題沒有收到解答，請再試一次。）";
        q.check = chk.trim() || null; q.source = "小安（AI，請老師確認）";
      });
      render(); XA.say("解題完成。AI 作答的題目都附自我檢查，仍請老師確認。");
    });
  }

  function addPractice() {
    var v = XA.fallVariant();
    var vertexA = [1, 2, -1][Math.floor(Math.random() * 3)], vh = Math.floor(Math.random() * 5) - 2, vk = Math.floor(Math.random() * 7) - 3;
    var vb = -2 * vertexA * vh, vc = vertexA * vh * vh + vk;
    D.extra = [
      { q: "類題 1：" + v.stem.replace(/？$/, "？") + "\n" + v.options.map(function (o) { return "(" + o.label + ") " + o.text; }).join("　"), a: "答案：(" + v.options.filter(function (o) { return o.correct; })[0].label + ")，t = √(2H ÷ g) ≈ " + num(v.t) + " 秒" + (v.selfCheck ? "（已驗算 ✓）" : "") },
      { q: "類題 2：求 y = " + vertexA + "x² " + (vb < 0 ? "− " + -vb : "+ " + vb) + "x " + (vc < 0 ? "− " + -vc : "+ " + vc) + " 的頂點坐標。", a: "答案：(" + vh + ", " + vk + ")（已驗算 ✓）" }];
    render(); XA.say("在文件最後加了兩題類題，答案也算好了。");
  }

  /* ---------- writing ---------- */
  function mkPara(doc, text, opts) {
    opts = opts || {};
    var p = doc.createElementNS(W, "w:p");
    String(text).split("\n").forEach(function (line, i) {
      var r = doc.createElementNS(W, "w:r");
      var rPr = doc.createElementNS(W, "w:rPr");
      if (opts.color) { var c = doc.createElementNS(W, "w:color"); c.setAttributeNS(W, "w:val", opts.color); rPr.appendChild(c); }
      if (opts.bold) rPr.appendChild(doc.createElementNS(W, "w:b"));
      if (opts.shade) { var sh = doc.createElementNS(W, "w:shd"); sh.setAttributeNS(W, "w:val", "clear"); sh.setAttributeNS(W, "w:color", "auto"); sh.setAttributeNS(W, "w:fill", opts.shade); rPr.appendChild(sh); }
      r.appendChild(rPr);
      if (i > 0) r.appendChild(doc.createElementNS(W, "w:br"));
      var t = doc.createElementNS(W, "w:t"); t.setAttribute("xml:space", "preserve"); t.textContent = line; r.appendChild(t);
      p.appendChild(r);
    });
    return p;
  }

  function buildNewDocx() {
    var zip = new JSZip();
    zip.file("[Content_Types].xml", '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>');
    zip.file("_rels/.rels", '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>');
    var xml = new DOMParser().parseFromString('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document xmlns:w="' + W + '"><w:body><w:sectPr/></w:body></w:document>', "application/xml");
    var body = xml.getElementsByTagNameNS(W, "body")[0], sect = body.lastChild;
    D.paras.forEach(function (p) { var n = mkPara(xml, p.text); body.insertBefore(n, sect); p.node = n; });
    return { zip: zip, xml: xml };
  }

  function save() {
    var hasWork = D.questions.some(function (q) { return q.solution; }) || D.extra.length;
    if (!hasWork) { XA.toast("還沒有要寫入的解答。先按「小安解題」。"); return; }
    var outName = D.name.replace(/\.docx$/i, "") + "_小安解題.docx";
    XA.confirm("把解答寫入 Word 並存檔？", "會另存成新檔「" + outName + "」" + (D.localPath && XA.local ? "，放在原檔同一個資料夾" : "") + "，原檔不會被覆蓋。共 " + D.questions.filter(function (q) { return q.solution && q.source !== "未作答"; }).length + " 題解答、" + D.extra.length + " 題類題。", "寫入並下載").then(function (yes) {
      if (!yes) return;
      var pkg = D.zip ? { zip: D.zip, xml: D.xml.cloneNode(true) } : buildNewDocx();
      var xml = pkg.xml;
      var paras = D.zip ? Array.from(xml.getElementsByTagNameNS(W, "body")[0].getElementsByTagNameNS(W, "p")) : D.paras.map(function (p) { return p.node; });
      // insert from the bottom up so earlier anchors stay valid
      D.questions.slice().reverse().forEach(function (q) {
        if (!q.solution || q.source === "未作答") return;
        var anchor = paras[q.end]; if (!anchor) return;
        var after = anchor.nextSibling, parent = anchor.parentNode;
        parent.insertBefore(mkPara(xml, q.solution, { color: "0D7A6A", shade: "E8F4F1" }), after);
        if (q.check) parent.insertBefore(mkPara(xml, q.check, { color: "2A66AD" }), after);
      });
      if (D.extra.length) {
        var body = xml.getElementsByTagNameNS(W, "body")[0];
        var sect = Array.from(body.childNodes).filter(function (n) { return n.localName === "sectPr"; })[0] || null;
        body.insertBefore(mkPara(xml, "小安出的類題", { bold: true }), sect);
        D.extra.forEach(function (e) { body.insertBefore(mkPara(xml, e.q), sect); body.insertBefore(mkPara(xml, e.a, { color: "0D7A6A" }), sect); });
      }
      pkg.zip.file("word/document.xml", new XMLSerializer().serializeToString(xml));
      return pkg.zip.generateAsync({ type: "blob", mimeType: "application/vnd.openxmlformats-officedocument.wordprocessingml.document" }).then(function (blob) {
        if (D.localPath && XA.local) {
          return XA.blobToBase64(blob).then(function (b64) {
            return XA.localCall("file_write", { path: D.localPath, name: outName, data: b64 });
          }).then(function (r) { XA.say("已存到「" + r.path + "」。"); })
            .catch(function (e) { XA.toast("本機存檔失敗：" + e.message + "，改為下載。"); XA.download(outName, blob); });
        }
        XA.download(outName, blob); XA.log("sys", "已存檔：" + outName);
      });
    });
  }

  /* ---------- view ---------- */
  var pageBox = null;
  function pageEl() {
    if (!D.paras.length) return h("div", { class: "doc-page" }, h("p", { style: { color: "#56635c" } }, "開啟一個 Word 檔，或貼上題目文字。"));
    var qAt = {}; D.questions.forEach(function (q) { qAt[q.end] = q; });
    var starts = {}; D.questions.forEach(function (q) { for (var i = q.at; i <= q.end; i++) starts[i] = true; });
    var kids = [];
    D.paras.forEach(function (p, i) {
      if (!p.text.trim()) return;
      kids.push(h("p", { class: starts[i] ? "q" : null }, p.text));
      var q = qAt[i];
      if (q && q.solution) { kids.push(h("p", { class: "sol new" }, q.solution)); if (q.check) kids.push(h("p", { class: "chk" }, q.check)); kids.push(h("p", { class: "chk", style: { color: "#56635c" } }, "— " + q.source)); }
    });
    if (D.extra.length) { kids.push(h("p", { class: "q" }, "小安出的類題")); D.extra.forEach(function (e) { kids.push(h("p", { style: { whiteSpace: "pre-wrap" } }, e.q)); kids.push(h("p", { class: "sol" }, e.a)); }); }
    return h("div", { class: "doc-page", "aria-label": "文件預覽" }, kids);
  }
  function render() { if (pageBox && pageBox.isConnected) XA.clear(pageBox).appendChild(pageEl()); else XA.render(); }

  XA.docsSolve = solveAll;
  XA.docsLoad = function (file, localPath) {
    return loadDocx(file, localPath).then(function () { XA.go("docs"); XA.say("讀到「" + file.name + "」，找到 " + D.questions.length + " 題。"); });
  };
  XA.views.docs = function (root) {
    root.appendChild(h("h2", { class: "view-title" }, "文件共編"));
    root.appendChild(h("p", { class: "view-sub" }, "讀取 Word 檔中的題目，把詳細解題過程與類題寫回文件；每題都附自我檢查。檔案只在你的瀏覽器裡處理。"));
    var fileIn = h("input", { type: "file", accept: ".docx,.txt,.md", class: "sr-only", id: "doc-file", onchange: function (e) {
      var f = e.target.files[0]; if (!f) return;
      var p = /\.docx$/i.test(f.name) ? loadDocx(f) : f.text().then(loadText);
      p.then(function () { XA.render(); XA.say("讀到「" + f.name + "」，找到 " + D.questions.length + " 題。"); }).catch(function (err) { XA.toast("讀取失敗：" + err.message); });
    } });
    var paste = h("textarea", { rows: 6, placeholder: "或把題目貼在這裡…" }, D.zip ? "" : D.paras.map(function (p) { return p.text; }).join("\n"));
    var ctl = h("div", { class: "panel" },
      h("h3", null, "1. 開啟文件"),
      fileIn,
      h("div", { class: "toolbar" }, h("label", { for: "doc-file", class: "xa-btn xa-btn-secondary", tabindex: 0, onkeydown: function (e) { if (e.key === "Enter") fileIn.click(); } }, "開啟 Word 檔（.docx）"),
        h("button", { class: "xa-btn xa-btn-quiet", onclick: function () { loadText(SAMPLE); XA.render(); } }, "載入範例練習卷")),
      h("p", { class: "xa-caption" }, D.name ? "目前：" + D.name + "（" + D.questions.length + " 題）" : "Google 文件請先「檔案 → 下載 → Microsoft Word」。"),
      h("div", { class: "field mt" }, paste),
      h("button", { class: "xa-btn xa-btn-quiet", onclick: function () { loadText(paste.value); XA.render(); } }, "使用貼上的文字"),
      h("h3", { class: "mt" }, "2. 小安作答"),
      h("div", { class: "toolbar" },
        h("button", { class: "xa-btn xa-btn-primary", disabled: D.busy || !D.questions.length, onclick: solveAll }, D.busy ? "小安解題中…" : "小安解題"),
        h("button", { class: "xa-btn xa-btn-secondary", disabled: !D.paras.length, onclick: addPractice }, "加入類題")),
      h("h3", { class: "mt" }, "3. 寫回 Word"),
      h("button", { class: "xa-btn xa-btn-primary", disabled: !D.paras.length, onclick: save }, "寫入並下載 .docx"),
      h("p", { class: "xa-caption", style: { marginTop: "8px" } }, "另存新檔，不覆蓋原檔；解答以青色標示、自我檢查以藍色標示。"));
    pageBox = h("div", null, pageEl());
    root.appendChild(h("div", { class: "grid2" }, ctl, pageBox));
  };
})();
