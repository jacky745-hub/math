/* 小安 Xiao-An — answer relay between student devices and the teacher console.
   - Same computer (other tabs/windows): BroadcastChannel, always on, nothing leaves the browser.
   - Across devices (phones): optional public relay ntfy.sh, OFF by default. Only the session code,
     an anonymous device id and the chosen option / short text are sent. */
(function () {
  var XA = window.XA;
  var RELAY = "https://ntfy.sh/";

  XA.relay = {
    topic: function (code, salt) { return "xiaoan-" + code + "-" + salt; },

    /* teacher side: listen for answers; returns a stop() function */
    listen: function (session, onAnswer) {
      var stops = [];
      try {
        var bc = new BroadcastChannel("xiaoan-" + session.code);
        bc.onmessage = function (e) { if (e.data && e.data.kind === "answer") onAnswer(e.data); };
        stops.push(function () { bc.close(); });
      } catch (e) { /* old browser */ }
      if (session.topic) {
        try {
          var es = new EventSource(RELAY + session.topic + "/sse");
          es.onmessage = function (e) {
            try {
              var m = JSON.parse(e.data);
              if (m.event !== "message") return;
              var d = JSON.parse(m.message);
              if (d && d.kind === "answer") onAnswer(d);
            } catch (err) { /* ignore noise */ }
          };
          es.onerror = function () { XA.emit("relay-error"); };
          stops.push(function () { es.close(); });
        } catch (e) { /* no EventSource */ }
      }
      return function () { stops.forEach(function (f) { f(); }); };
    },

    /* student side */
    send: function (payload, topic) {
      var sent = [];
      try { var bc = new BroadcastChannel("xiaoan-" + payload.code); bc.postMessage(payload); bc.close(); sent.push("local"); } catch (e) { /* */ }
      if (!topic) return Promise.resolve(sent);
      return fetch(RELAY + topic, { method: "POST", body: JSON.stringify(payload) })
        .then(function (r) { if (!r.ok) throw new Error("HTTP " + r.status); sent.push("relay"); return sent; });
    }
  };
})();
