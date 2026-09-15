/* LEVI PWA — chat client. No build step, no dependencies. */
(function () {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const chat = $("chat"), input = $("input"), sendBtn = $("sendBtn");
  const registerSel = $("register"), sessionInput = $("session");
  const modelName = $("modelName"), modelNote = $("modelNote");
  const statusBadge = $("statusBadge"), offlineBanner = $("offlineBanner");
  const providerDot = $("providerDot"), providerName = $("providerName");

  const store = {
    get(k, d) { try { const v = localStorage.getItem("levi.pwa." + k); return v === null ? d : v; } catch (e) { return d; } },
    set(k, v) { try { localStorage.setItem("levi.pwa." + k, v); } catch (e) {} },
  };

  let token = store.get("token", "");
  let busy = false;

  function headers(extra) {
    const h = Object.assign({ "Content-Type": "application/json" }, extra || {});
    if (token) h["Authorization"] = "Bearer " + token;
    return h;
  }

  async function api(path, opts) {
    const r = await fetch(path, opts);
    if (r.status === 401) {
      const t = prompt("This LEVI server needs a token (LEVI_PWA_TOKEN):");
      if (t) { token = t.trim(); store.set("token", token); return api(path, opts); }
      throw new Error("unauthorized");
    }
    if (!r.ok) {
      let msg = "HTTP " + r.status;
      try { const j = await r.json(); if (j.error) msg = j.error; } catch (e) {}
      throw new Error(msg);
    }
    return r;
  }

  function setOnline(ok) {
    offlineBanner.classList.toggle("hidden", ok);
    providerDot.className = "dot " + (ok ? "ok" : "bad");
    statusBadge.textContent = ok ? "server reachable" : "server unreachable";
  }

  function addMsg(role, text, meta) {
    const d = document.createElement("div");
    d.className = "msg " + role;
    const body = document.createElement("div");
    body.textContent = text;
    d.appendChild(body);
    if (meta) {
      const m = document.createElement("div");
      m.className = "meta";
      m.textContent = meta;
      d.appendChild(m);
    }
    chat.appendChild(d);
    chat.scrollTop = chat.scrollHeight;
    return d;
  }

  function addImage(url, prompt, meta) {
    const d = document.createElement("div");
    d.className = "msg levi";
    const cap = document.createElement("div");
    cap.textContent = "🖼 " + prompt;
    d.appendChild(cap);
    const img = document.createElement("img");
    img.className = "gen";
    img.src = url;
    img.alt = prompt;
    img.loading = "lazy";
    d.appendChild(img);
    if (meta) {
      const m = document.createElement("div");
      m.className = "meta";
      m.textContent = meta;
      d.appendChild(m);
    }
    chat.appendChild(d);
    chat.scrollTop = chat.scrollHeight;
  }

  function setBusy(b) {
    busy = b;
    sendBtn.disabled = b;
    input.disabled = b;
  }

  /* ---- bootstrap: registers, models, health ---- */
  async function bootstrap() {
    try {
      const regs = await (await api("/api/registers")).json();
      registerSel.innerHTML = "";
      (regs.registers || []).forEach((r) => {
        const o = document.createElement("option");
        o.value = r.id;
        o.textContent = r.name;
        o.title = r.tagline || "";
        registerSel.appendChild(o);
      });
      const saved = store.get("register", "kai_9000");
      if ([...registerSel.options].some((o) => o.value === saved)) registerSel.value = saved;
    } catch (e) { /* registers stay empty; chat still works */ }

    try {
      const m = await (await api("/api/models")).json();
      const r = m.resolved;
      if (r) {
        modelName.textContent = r.entry;
        modelNote.textContent = (r.provider || "") + " — " + (r.reason || "");
      } else {
        modelName.textContent = "rules planner";
        modelNote.textContent = "No LEVI weights downloaded — deterministic fallback. `levi agent model pull` to upgrade.";
      }
      providerName.textContent = (r && r.provider) || "local";
      setOnline(true);
    } catch (e) {
      setOnline(false);
      modelName.textContent = "unknown";
      modelNote.textContent = "Could not reach the LEVI server.";
    }
  }

  /* ---- chat ---- */
  function sseReply(payload, onDone, onError) {
    // POST /api/chat/stream with fetch + ReadableStream (EventSource can't POST).
    fetch("/api/chat/stream", {
      method: "POST",
      headers: headers(),
      body: JSON.stringify(payload),
    }).then((r) => {
      if (!r.ok) throw new Error("HTTP " + r.status);
      const reader = r.body.getReader();
      const dec = new TextDecoder();
      let buf = "", event = "";
      function pump() {
        return reader.read().then(({ done, value }) => {
          if (done) return;
          buf += dec.decode(value, { stream: true });
          let idx;
          while ((idx = buf.indexOf("\n\n")) >= 0) {
            const raw = buf.slice(0, idx);
            buf = buf.slice(idx + 2);
            let data = "";
            raw.split("\n").forEach((line) => {
              if (line.startsWith("event:")) event = line.slice(6).trim();
              else if (line.startsWith("data:")) data += line.slice(5).trim();
            });
            if (event === "done") { onDone(JSON.parse(data)); return; }
            if (event === "error") { onError(new Error(JSON.parse(data).error || "stream error")); return; }
            // "status" events: liveness only — the typing indicator already covers it.
          }
          return pump();
        });
      }
      return pump();
    }).catch(onError);
  }

  function plainReply(payload) {
    return api("/api/chat", { method: "POST", headers: headers(), body: JSON.stringify(payload) })
      .then((r) => r.json());
  }

  function send(text) {
    text = (text || "").trim();
    if (!text || busy) return;
    input.value = "";

    // local slash commands
    if (text === "/help") {
      addMsg("sys", "Commands:\n/image <prompt> — generate an image (cloud-backed)\n/register <id> — switch register\n/clear — clear this view (history stays on the server)\nEverything else goes to LEVI.");
      return;
    }
    if (text === "/clear") { chat.innerHTML = ""; return; }
    if (text.startsWith("/register ")) {
      const id = text.slice(10).trim();
      const opt = [...registerSel.options].find((o) => o.value === id);
      if (opt) { registerSel.value = id; store.set("register", id); addMsg("sys", "Register: " + opt.textContent); }
      else addMsg("sys", "Unknown register. Pick one from the sidebar.");
      return;
    }
    if (text.startsWith("/image ")) {
      const prompt = text.slice(7).trim();
      if (!prompt) { addMsg("sys", "Usage: /image <prompt>"); return; }
      doImage(prompt);
      return;
    }

    addMsg("user", text);
    const typing = document.createElement("div");
    typing.className = "typing";
    typing.textContent = "LEVI is thinking";
    chat.appendChild(typing);
    chat.scrollTop = chat.scrollHeight;
    setBusy(true);

    const payload = {
      session: sessionInput.value.trim() || "default",
      message: text,
      register: registerSel.value || null,
      consent: false,
    };
    const finish = (res) => {
      typing.remove();
      setBusy(false);
      setOnline(true);
      store.set("session", payload.session);
      const meta = [res.provider, res.steps + " steps",
        Math.round((res.context_pct || 0) * 100) + "% ctx"]
        .filter(Boolean).join(" · ");
      addMsg("levi", res.reply || "(empty reply)", meta + (res.compressed ? " · compressed" : ""));
      providerName.textContent = res.provider || "";
    };
    const fail = (err) => {
      typing.remove();
      setBusy(false);
      setOnline(false);
      addMsg("levi", "Turn failed: " + (err && err.message ? err.message : err), "error").classList.add("error");
    };

    // Prefer SSE; fall back to plain JSON if streaming fails.
    let streamed = false;
    try {
      sseReply(payload,
        (res) => { streamed = true; finish(res); },
        () => { if (!streamed) plainReply(payload).then(finish).catch(fail); });
    } catch (e) {
      plainReply(payload).then(finish).catch(fail);
    }
  }

  function doImage(prompt) {
    addMsg("user", "/image " + prompt);
    setBusy(true);
    api("/api/image", { method: "POST", headers: headers(), body: JSON.stringify({ prompt }) })
      .then((r) => r.json())
      .then((img) => {
        setBusy(false);
        setOnline(true);
        addImage(img.url, prompt, "seed " + img.seed + " · " + img.model + (img.path ? " · saved " + img.path : ""));
      })
      .catch((err) => {
        setBusy(false);
        addMsg("levi", "Image failed: " + (err && err.message ? err.message : err)).classList.add("error");
      });
  }

  /* ---- wiring ---- */
  sendBtn.addEventListener("click", () => send(input.value));
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(input.value); }
  });
  registerSel.addEventListener("change", () => store.set("register", registerSel.value));
  sessionInput.value = store.get("session", "default");
  sessionInput.addEventListener("change", () => store.set("session", sessionInput.value.trim() || "default"));
  $("menuBtn").addEventListener("click", () => $("sidebar").classList.toggle("open"));

  if ("serviceWorker" in navigator) {
    window.addEventListener("load", () => {
      navigator.serviceWorker.register("/sw.js").catch(() => {});
    });
  }

  bootstrap().then(() => {
    addMsg("sys", "LEVI PWA ready. Talk, or try /help.");
  });
})();
