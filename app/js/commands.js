/* 小安 Xiao-An — understanding what the teacher says or types.
   Local intents first (work offline, instant); anything else goes to the language model if connected. */
(function () {
  var XA = window.XA;
  var history = [];

  var INTENTS = [
    { re: /^(?:請)?(?:記住|記得|幫我記)[:：，,]?\s*(.+)$/, run: function (m) { return rememberSay(m[1]); } },
    { re: /^我(?:比較)?(?:喜歡|習慣|偏好)(.+)$/, run: function (m, t) { return rememberSay(t.replace(/^我/, "")); } },
    { re: /忘記.*(?:習慣|記憶)|清除記憶/, run: function () { XA.go("settings"); XA.say("記住的習慣在這裡，可以逐一刪除。"); } },

    { re: /模擬|預演/, run: function () { if (!XA.quiz.session) XA.quizDispatch(); XA.quizSimulate(30); XA.say("已模擬 30 位同學作答。"); } },
    { re: /統計|結果|答對率|分析.*(?:答案|迷思)/, run: function () { XA.quizFinish(); } },
    { re: /派發|發.*題|QR|測驗/i, run: function (m, t) {
      var pick = /二次|頂點/.test(t) ? "vertex" : /血管|動脈/.test(t) ? "artery" : /觀念|開放|文字雲|想法/.test(t) ? "open-fall" : /自由落|落體/.test(t) ? "fall" : null;
      var b = pick && XA.quizBank.filter(function (x) { return x.id === pick; })[0];
      XA.quizDispatch(b || null);
    } },

    { re: /下一步|繼續|然後呢/, run: function () { if (XA.current !== "board") XA.go("board"); XA.boardStep(1); } },
    { re: /上一步|回去/, run: function () { if (XA.current !== "board") XA.go("board"); XA.boardStep(-1); } },
    { re: /類題|再出一題|練習題/, run: function () {
      if (XA.current === "docs") { XA.$("#view").querySelectorAll("button").forEach(function (b) { if (b.textContent === "加入類題") b.click(); }); return; }
      var v = XA.fallVariant(); XA.quiz.draft = v; XA.go("quiz"); XA.say("出了一題類題：" + v.stem + " 要派發嗎？", [{ label: "派發", variant: "primary", run: function () { XA.quizDispatch(); } }]);
    } },
    { re: /(?:自由落體|落下).*?(\d+(?:\.\d+)?)\s*(?:公尺|m)|(\d+(?:\.\d+)?)\s*(?:公尺|m).*(?:落|推導)/, run: function (m) {
      XA.board.tpl = "fall"; XA.board.p = { H: +(m[1] || m[2]), g: 9.8 }; XA.board.cur = 0; XA.board.practice = null; XA.go("board"); XA.boardStep(0);
    } },
    { re: /推導|黑板|自由落體/, run: function () { XA.go("board"); XA.boardStep(0); } },

    { re: /y\s*=\s*([-−+0-9x²^.\s*/()a-z]+)/i, run: function (m) {
      var q = XA.parseQuadratic(m[1]);
      if (q) { XA.graph.a = q.a; XA.graph.b = q.b; XA.graph.c = q.c; XA.graph.expr = ""; }
      else XA.graph.expr = m[1].trim();
      XA.go("graph"); XA.say("畫好了 y = " + m[1].trim() + (q ? "，頂點、焦點都標出來了。" : "。"));
    } },
    { re: /函數|拋物線|繪圖|畫.*圖形/, run: function () { XA.go("graph"); XA.say("可以直接跟我說式子，例如「畫 y = x² − 4x + 3」。"); } },

    { re: /血管|動脈|血球/, run: function () { XA.visualShow("artery"); } },
    { re: /馬克杯|杯子/, run: function () { XA.visualShow("mug"); } },
    { re: /(?:畫|生成|產生|投影)(?:一[張個])?(.+?)(?:的)?(?:示意圖|3D|圖)$/, run: function (m) { XA.go("visual"); XA.visualGenerate(m[1]); } },

    { re: /解題|作答|批改|寫進\s*word|word/i, run: function () { XA.go("docs"); if (XA.docs.questions.length) XA.docsSolve(); else XA.say("請先開啟 Word 檔或載入範例練習卷。"); } },

    { re: /從(.+?)(?:到|去)(.+?)(?:要多久|多久|怎麼走|的路線|路線|車程)?[？?。]?$/, run: function (m) { XA.openMaps(m[1].trim(), m[2].trim(), "driving"); } },
    { re: /地圖|導航|路線/, run: function () { XA.go("tools"); } },
    { re: /^(?:請|幫我)?播放\s*(.*?)(?:的)?(?:音樂|歌曲?)?$/, run: function (m) { XA.openSpotify(m[1].replace(/spotify|一些|一點/gi, "").trim() || "lofi"); } },
    { re: /geogebra/i, run: function () { XA.openLink("開啟 GeoGebra 計算機", "https://www.geogebra.org/calculator?lang=zh-TW"); } },
    { re: /寄信|寄.*(?:郵件|摘要|家長)|email|行事曆|行程|簡報/i, run: function () { XA.go("tools"); XA.say("工具都在這裡，確認內容後我再幫你開啟。"); } },

    { re: /全螢幕|投影/, run: function () { XA.projectCurrent(); } },
    { re: /深色|暗|投影模式/, run: function () { XA.setTheme("dark"); } },
    { re: /淺色|亮/, run: function () { XA.setTheme("light"); } },
    { re: /^(?:你會什麼|你可以做什麼|幫助|help|說明)/i, run: function () { help(); } }
  ];

  function rememberSay(fact) {
    if (XA.remember(fact)) XA.say("好，我記住了：" + fact.trim() + "。之後會自動套用。");
    else XA.say("這個我已經記得了。");
  }
  function help() {
    XA.say("你可以這樣跟我說：\n・派發自由落體的題目／模擬全班作答／統計結果\n・推導 45 公尺的自由落體／下一步／出一題類題\n・畫 y = x² − 4x + 3\n・投影動脈血管／畫一張植物細胞的示意圖\n・幫我解題（文件共編）\n・從光武國中到清華大學要多久\n・記住：我喜歡用生活實例");
  }

  XA.handle = function (text) {
    text = String(text || "").trim();
    if (!text) return;
    XA.log("me", text);
    var all = (XA.preIntents || []).concat(INTENTS);
    for (var i = 0; i < all.length; i++) {
      var m = text.match(all[i].re);
      if (m) { try { all[i].run(m, text); } catch (e) { console.error(e); XA.say("這個動作沒有成功：" + e.message); } return; }
    }
    if (!XA.hasLLM()) {
      XA.say("我還不確定要做什麼。連上語言模型後我能自由對話；現在可以說「你會什麼」看看我會的指令。");
      return;
    }
    var ctx = "老師目前在「" + (XA.viewNames[XA.current] || XA.current) + "」畫面。";
    if (XA.quiz.session) ctx += "目前題目：" + XA.quiz.session.quiz.stem + "。" + (XA.quizStats().total ? "已有 " + XA.quizStats().total + " 人作答。" : "");
    XA.ask(text, { history: history.slice(-10), system: ctx }).then(function (t) {
      history.push({ role: "user", content: XA.redact(text).text }, { role: "assistant", content: t });
      XA.say(t);
    }).catch(function (e) { XA.say("連線語言模型失敗：" + e.message); });
  };
})();
