/* focus-flow cell — local ambient pad for coding sessions.
 *
 * Real playback, honestly labeled: the pad is synthesized in the cell
 * with Web Audio where the host exposes it (feature-detected — cells
 * run in a Worker, and not every host exposes AudioContext there).
 * When audio is unavailable the cell says so and points at the engine
 * side (levi.si.plugins.focus_flow FocusSession.render), which writes
 * a real playable WAV. No network at any point — a focus pad, not
 * licensed music.
 *
 * Authoring contract: defineCellPlugin(activate) with the sealed cell
 * API { call, registerCommand, unregisterCommand, onCommand, notify }.
 */

defineCellPlugin(function (cell) {
  var actx = null;
  var padNodes = []; // {osc, gain}
  var noise = null;  // {src, gain}
  var chordIdx = 0;

  var CHORDS = [
    { name: "Am", freqs: [220.0, 261.63, 329.63] },
    { name: "F", freqs: [174.61, 220.0, 261.63] },
    { name: "C", freqs: [130.81, 164.81, 196.0] },
    { name: "G", freqs: [196.0, 246.94, 293.66] },
  ];

  function audioCtor() {
    if (typeof self === "undefined") return null;
    return self.AudioContext || self.webkitAudioContext || null;
  }

  function ensureCtx() {
    var AC = audioCtor();
    if (!AC) return null;
    if (!actx) actx = new AC();
    if (actx.state === "suspended") actx.resume();
    return actx;
  }

  function fadeOut(nodes, delayMs) {
    if (!actx) { nodes.length = 0; return; }
    var t = actx.currentTime;
    nodes.forEach(function (n) {
      try {
        n.gain.gain.cancelScheduledValues(t);
        n.gain.gain.setValueAtTime(n.gain.gain.value, t);
        n.gain.gain.linearRampToValueAtTime(0.0001, t + 0.8);
        var stoppable = n.osc || n.src;
        setTimeout(function () { try { stoppable.stop(); } catch (e) {} }, 900);
      } catch (e) {}
    });
    setTimeout(function () { nodes.length = 0; }, delayMs || 950);
  }

  function buildPad(chord) {
    var ctx = ensureCtx();
    if (!ctx) return false;
    var t = ctx.currentTime;
    var master = ctx.createGain();
    master.gain.setValueAtTime(0.0001, t);
    master.gain.linearRampToValueAtTime(0.9, t + 4);
    var lp = ctx.createBiquadFilter();
    lp.type = "lowpass";
    lp.frequency.value = 900;
    master.connect(lp);
    lp.connect(ctx.destination);

    chord.freqs.forEach(function (f) {
      [f, f * 1.003].forEach(function (ff) {
        var osc = ctx.createOscillator();
        osc.type = "sine";
        osc.frequency.value = ff;
        var g = ctx.createGain();
        g.gain.value = 0.05;
        osc.connect(g);
        g.connect(master);
        osc.start();
        padNodes.push({ osc: osc, gain: g });
      });
    });

    var len = Math.floor(ctx.sampleRate * 2);
    var buf = ctx.createBuffer(1, len, ctx.sampleRate);
    var d = buf.getChannelData(0);
    var last = 0;
    for (var i = 0; i < len; i++) {
      var white = Math.random() * 2 - 1;
      last = (last + 0.02 * white) / 1.02;
      d[i] = last * 3.0;
    }
    var src = ctx.createBufferSource();
    src.buffer = buf;
    src.loop = true;
    var ng = ctx.createGain();
    ng.gain.value = 0.05;
    var nlp = ctx.createBiquadFilter();
    nlp.type = "lowpass";
    nlp.frequency.value = 400;
    src.connect(ng);
    ng.connect(nlp);
    nlp.connect(ctx.destination);
    src.start();
    noise = { src: src, gain: ng };
    return true;
  }

  function startFlow() {
    fadeOut(padNodes);
    if (noise) { fadeOut([noise]); noise = null; }
    var chord = CHORDS[chordIdx];
    if (!buildPad(chord)) {
      cell.notify(
        "focus flow: this host does not expose audio to cells — " +
        "render a session WAV with levi.si.plugins.focus_flow instead.",
        "error"
      );
      return { playing: false, reason: "audio-unavailable" };
    }
    cell.notify(
      "focus flow playing — pad " + chord.name +
      " (" + (chordIdx + 1) + "/4). next steps the chord.",
      "info"
    );
    return { playing: true, chord: chord.name };
  }

  function stopFlow() {
    fadeOut(padNodes);
    if (noise) { fadeOut([noise]); noise = null; }
    cell.notify("focus flow stopped.", "info");
    return { playing: false };
  }

  cell.registerCommand({ id: "focus-flow.start", title: "Focus Flow: start pad", category: "Focus" });
  cell.registerCommand({ id: "focus-flow.stop", title: "Focus Flow: stop pad", category: "Focus" });
  cell.registerCommand({ id: "focus-flow.next", title: "Focus Flow: next chord", category: "Focus" });

  cell.onCommand("focus-flow.start", function () { return startFlow(); });
  cell.onCommand("focus-flow.stop", function () { return stopFlow(); });
  cell.onCommand("focus-flow.next", function () {
    chordIdx = (chordIdx + 1) % CHORDS.length;
    return startFlow();
  });
});
