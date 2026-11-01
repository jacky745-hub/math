/* 小安 Xiao-An — 系統與應用程式操控 + 設定與記憶. Every outward action goes through XA.confirm. */
(function () {
  var XA = window.XA, h = XA.h;
  var T = XA.store.get("tools", { from: "新竹市立光武國民中學", to: "國立清華大學", mode: "driving", slides: "", mail: "", spotify: "古典音樂 專注", web: "" });
  function saveT() { XA.store.set("tools", T); }
  XA.toolsState = T;

  XA.mapsUrl = function (from, to, mode) {
    return "https://www.google.com/maps/dir/?api=1&origin=" + encodeURIComponent(from) + "&destination=" + encodeURIComponent(to) + "&travelmode=" + (mode || "driving");
  };
  XA.openMaps = function (from, to, mode) {
    var M = { driving: "開車", transit: "大眾運輸", walking: "步行", bicycling: "騎單車" };
    return XA.openLink("規劃路線：" + from + " → " + to, XA.mapsUrl(from, to, mode), "在 Google 地圖開啟" + (M[mode] || "開車") + "路線，查看車程時間、距離與路線。");
  };
  XA.openSpotify = function (q) { return XA.openLink("在 Spotify 播放「" + q + "」", "https://open.spotify.com/search/" + encodeURIComponent(q), "在新分頁開啟 Spotify 搜尋結果，由你按下播放。"); };

  function summaryText() {
    var st = XA.quizStats && XA.quizStats();
    if (!st || !st.total) return "本節課尚未有測驗資料。";
    var q = XA.quiz.session.quiz;
    return "本節課測驗摘要\n題目：" + q.stem + "\n作答人數：" + st.total + (st.rate != null ? "\n答對率：" + st.rate + "%" : "") + "\n小安的觀察：" + XA.quizInsight();
  }

  function section(title, sub, body) { return h("div", { class: "panel" }, h("h3", null, title), sub ? h("p", { class: "xa-caption", style: { marginBottom: "12px" } }, sub) : null, body); }
  function input(key, label, ph) { return h("div", { class: "field" }, label, h("input", { value: T[key] || "", placeholder: ph || "", oninput: function (e) { T[key] = e.target.value; saveT(); } })); }

  XA.views.tools = function (root) {
    root.appendChild(h("h2", { class: "view-title" }, "工具與操控"));
    root.appendChild(h("p", { class: "view-sub" }, "簡報、地圖、行事曆、郵件、音樂與外部教學網站。每個動作都會先問過你。"));

    var slides = section("簡報控制", "開啟直播簡報，或控制小安的投影畫面。快捷鍵：F 全螢幕、P 投影目前畫面、← → 換步驟、Esc 結束。", h("div", null,
      input("slides", "簡報網址（Google 簡報／PowerPoint Online）", "https://docs.google.com/presentation/d/…"),
      h("div", { class: "toolbar" },
        h("button", { class: "xa-btn xa-btn-primary", onclick: function () {
          if (!T.slides) { XA.toast("請先貼上簡報網址。"); return; }
          var url = T.slides.replace(/\/edit.*$/, "/present");
          if (!/^https:\/\//.test(url)) { XA.toast("網址需要以 https:// 開頭。"); return; }
          XA.openLink("開啟直播簡報", url, "在新視窗開啟簡報播放模式：" + url);
        } }, "開啟簡報"),
        h("button", { class: "xa-btn xa-btn-secondary", onclick: XA.toggleFullscreen }, "切換全螢幕"),
        h("button", { class: "xa-btn xa-btn-secondary", onclick: function () { XA.zoom(0.1); } }, "放大"),
        h("button", { class: "xa-btn xa-btn-secondary", onclick: function () { XA.zoom(-0.1); } }, "縮小"),
        h("button", { class: "xa-btn xa-btn-quiet", onclick: function () { XA.zoom(0); } }, "還原"))));

    var modeSel = h("select", { onchange: function (e) { T.mode = e.target.value; saveT(); } }, [["driving", "開車"], ["transit", "大眾運輸"], ["walking", "步行"], ["bicycling", "騎單車"]].map(function (m) { return h("option", { value: m[0], selected: T.mode === m[0] }, m[1]); }));
    var maps = section("地圖與導航", "用 Google 地圖計算車程時間、距離與路線。", h("div", null,
      h("div", { class: "row" }, input("from", "出發地"), input("to", "目的地")),
      h("div", { class: "row" }, h("div", { class: "field" }, "交通方式", modeSel),
        h("button", { class: "xa-btn xa-btn-primary", style: { marginBottom: "12px" }, onclick: function () { XA.openMaps(T.from, T.to, T.mode); } }, "規劃路線"))));

    var calTitle = h("input", { value: "八年三班 自由落體 補救教學" }), calDate = h("input", { type: "date", value: new Date(Date.now() + 864e5).toISOString().slice(0, 10) }), calTime = h("input", { type: "time", value: "10:00" });
    var cal = section("行程日曆", "在 Google 日曆建立一個 50 分鐘的行程，存檔前你可以再修改。", h("div", null,
      h("div", { class: "field" }, "標題", calTitle), h("div", { class: "row" }, h("div", { class: "field" }, "日期", calDate), h("div", { class: "field" }, "時間", calTime)),
      h("button", { class: "xa-btn xa-btn-primary", onclick: function () {
        var st = new Date(calDate.value + "T" + calTime.value), en = new Date(st.getTime() + 50 * 6e4);
        function f(d) { return d.toISOString().replace(/[-:]/g, "").replace(/\.\d{3}/, ""); }
        XA.openLink("新增行程：" + calTitle.value, "https://calendar.google.com/calendar/render?action=TEMPLATE&text=" + encodeURIComponent(calTitle.value) + "&dates=" + f(st) + "/" + f(en) + "&details=" + encodeURIComponent("由小安建立"),
          calDate.value + " " + calTime.value + "，50 分鐘。會開啟 Google 日曆的新增畫面，由你按儲存。");
      } }, "建立行程")));

    var mailBody = h("textarea", { rows: 6 }, summaryText());
    var mailSubj = h("input", { value: "本節課測驗摘要" });
    var mail = section("寄送郵件", "把本節課的答題摘要寄給家長、同事或自己。只包含統計，不含學生個資。", h("div", null,
      input("mail", "收件人", "name@example.com"), h("div", { class: "field" }, "主旨", mailSubj), h("div", { class: "field" }, "內容", mailBody),
      h("div", { class: "toolbar" },
        h("button", { class: "xa-btn xa-btn-quiet", onclick: function () { mailBody.value = summaryText(); } }, "更新摘要"),
        h("button", { class: "xa-btn xa-btn-primary", onclick: function () {
          var body = XA.redact(mailBody.value).text;
          XA.confirm("寄出這封信？", "收件人：" + (T.mail || "（未填，開啟後再填）") + "\n主旨：" + mailSubj.value + "\n會開啟你的郵件程式，由你按下傳送。", "開啟郵件").then(function (yes) {
            if (yes) location.href = "mailto:" + encodeURIComponent(T.mail || "") + "?subject=" + encodeURIComponent(mailSubj.value) + "&body=" + encodeURIComponent(body);
          });
        } }, "寄送"))));

    var music = section("音樂", "上課前暖場或自習時播放。", h("div", null, input("spotify", "想聽什麼"),
      h("button", { class: "xa-btn xa-btn-primary", onclick: function () { XA.openSpotify(T.spotify || "lofi"); } }, "在 Spotify 播放")));

    var sites = [["GeoGebra 計算機", "https://www.geogebra.org/calculator?lang=zh-TW"], ["GeoGebra 3D", "https://www.geogebra.org/3d?lang=zh-TW"], ["PhET 自由落體模擬", "https://phet.colorado.edu/zh_TW/simulations/projectile-motion"], ["Google 雲端硬碟", "https://drive.google.com/"]];
    var web = section("外部教學網站", "開啟協作網站或討論版。", h("div", null,
      h("div", { class: "toolbar" }, sites.map(function (x) { return h("button", { class: "xa-btn xa-btn-secondary", onclick: function () { XA.openLink("開啟 " + x[0], x[1]); } }, x[0]); })),
      h("div", { class: "row" }, input("web", "其他網址", "https://…"), h("button", { class: "xa-btn xa-btn-primary", style: { marginBottom: "12px" }, onclick: function () {
        if (!/^https?:\/\//.test(T.web || "")) { XA.toast("請輸入以 https:// 開頭的網址。"); return; }
        XA.openLink("開啟網站", T.web);
      } }, "開啟"))));

    root.appendChild(h("div", { class: "grid2" }, h("div", { class: "xa-stack" }, slides, maps, cal), h("div", { class: "xa-stack" }, mail, music, web)));
    var note = h("p", { class: "xa-caption mt" }, "說明：瀏覽器版的小安會在新分頁開啟這些服務，由你完成最後一步。直接控制 Mac 本機程式（Keynote、Spotify App、檔案總管）需要本機版。");
    root.appendChild(note);
  };

  /* ---------- settings & memory ---------- */
  XA.views.settings = function (root) {
    var S = XA.settings;
    root.appendChild(h("h2", { class: "view-title" }, "設定與記憶"));
    root.appendChild(h("p", { class: "view-sub" }, "連接語言模型、語音、跨裝置作答，以及小安記住的教學習慣。"));
    function bind(key, el, prop) { el.addEventListener("change", function () { S[key] = prop === "checked" ? el.checked : el.value.trim(); XA.saveSettings(); XA.emit("settings"); }); return el; }

    var keyIn = bind("apiKey", h("input", { type: "password", value: S.apiKey, placeholder: "sk-ant-…", autocomplete: "off" }));
    var llm = h("div", { class: "panel" }, h("h3", null, "語言模型（選用）"),
      h("p", { class: "xa-caption", style: { marginBottom: "12px" } }, "填入 Claude API 金鑰後，小安可以自由對話、分析迷思、解任意題目、出類題與畫示意圖。不填也能使用公式解題、統計、黑板、繪圖與投影。"),
      h("div", { class: "field" }, "Claude API 金鑰", keyIn, h("span", { class: "hint" }, "只存在這台電腦的瀏覽器裡，直接送到 Anthropic。請勿在公用電腦儲存。")),
      h("div", { class: "field" }, "模型", bind("model", h("input", { value: S.model }))),
      h("div", { class: "toolbar" }, h("button", { class: "xa-btn xa-btn-secondary", onclick: function () {
        XA.ask("用一句話跟老師打招呼。").then(function (t) { XA.say(t); XA.toast("連線成功"); }).catch(function (e) { XA.toast(e.message === "NO_KEY" ? "請先填金鑰。" : "連線失敗：" + e.message); });
      } }, "測試連線"), h("button", { class: "xa-btn xa-btn-quiet", onclick: function () { S.apiKey = ""; XA.saveSettings(); XA.render(); } }, "清除金鑰")));

    var voice = h("div", { class: "panel" }, h("h3", null, "語音與畫面"),
      h("label", { class: "check" }, bind("voice", h("input", { type: "checkbox", checked: S.voice }), "checked"), "小安說話時唸出來"),
      h("div", { class: "field" }, "語言", bind("lang", h("select", null, [["zh-TW", "中文（台灣）"], ["en-US", "English（口譯模式）"]].map(function (l) { return h("option", { value: l[0], selected: S.lang === l[0] }, l[1]); })))),
      h("label", { class: "check" }, bind("proactive", h("input", { type: "checkbox", checked: S.proactive }), "checked"), "讓小安主動提醒（例如全班作答完畢）"),
      h("p", { class: "xa-caption" }, XA.canListen ? "語音輸入可用：按上方麥克風或空白鍵說話。" : "這個瀏覽器不支援語音輸入；請用 Chrome 或 Edge。"));

    var relay = h("div", { class: "panel" }, h("h3", null, "學生作答"),
      h("label", { class: "check" }, bind("relay", h("input", { type: "checkbox", checked: S.relay }), "checked"), "跨裝置作答（學生用自己的手機）"),
      h("p", { class: "xa-caption", style: { marginBottom: "12px" } }, "開啟後，答案會經由公開中繼服務 ntfy.sh 傳回老師端：只傳送隨機代碼與選項，不含姓名。關閉時只有同一台電腦的其他分頁能作答（適合預演）。"),
      h("div", { class: "field" }, "學生作答頁網址（選填）", bind("baseUrl", h("input", { value: S.baseUrl, placeholder: "例如 https://你的帳號.github.io/math/app/" })),
        h("span", { class: "hint" }, "QR Code 會指向這個網址的 student.html。留空時使用目前網址；手機要能連到這個網址。")));

    var memList = h("ul", { class: "memory-list" });
    function drawMem() {
      XA.clear(memList);
      if (!XA.memory.length) memList.appendChild(h("li", null, "還沒有記住任何習慣。"));
      XA.memory.forEach(function (m, i) { memList.appendChild(h("li", null, m, h("button", { class: "xa-btn xa-btn-quiet", "aria-label": "忘記：" + m, onclick: function () { XA.forget(i); drawMem(); } }, "忘記"))); });
    }
    drawMem();
    var memIn = h("input", { placeholder: "例如：解釋時多用運動的例子" });
    var mem = h("div", { class: "panel" }, h("h3", null, "小安記住的習慣"),
      h("p", { class: "xa-caption", style: { marginBottom: "12px" } }, "對話中說「記住…」或「我喜歡…」，小安就會記下來，之後自動套用。"),
      memList,
      h("div", { class: "row mt" }, h("div", { class: "field" }, memIn), h("button", { class: "xa-btn xa-btn-secondary", style: { marginBottom: "12px" }, onclick: function () { if (XA.remember(memIn.value)) { memIn.value = ""; drawMem(); } } }, "新增")));

    var privacy = h("div", { class: "panel" }, h("h3", null, "安全與隱私"),
      h("ul", { style: { margin: 0, paddingLeft: "20px", fontSize: "15px", lineHeight: "26px" } },
        h("li", null, "送給語言模型前，自動遮蔽身分證字號、密碼、卡號與金鑰。"),
        h("li", null, "寄信、存檔、開啟外部網站、切換服務前一定先問你。"),
        h("li", null, "學生作答只有隨機代碼，沒有姓名；文字雲與統計只顯示整體結果。"),
        h("li", null, "所有資料存在這台電腦的瀏覽器，可隨時清除。")),
      h("button", { class: "xa-btn xa-btn-secondary mt", onclick: function () {
        XA.confirm("清除小安在這台電腦的所有資料？", "包含 API 金鑰、記住的習慣與設定。無法復原。", "全部清除").then(function (yes) {
          if (!yes) return;
          try { Object.keys(localStorage).filter(function (k) { return k.indexOf("xa.") === 0; }).forEach(function (k) { localStorage.removeItem(k); }); } catch (e) { /* */ }
          location.reload();
        });
      } }, "清除所有資料"));
    root.appendChild(h("div", { class: "grid2" }, h("div", { class: "xa-stack" }, llm, voice, relay), h("div", { class: "xa-stack" }, mem, privacy)));
  };
})();
