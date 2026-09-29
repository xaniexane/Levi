"""Buzz Tunes — Chauncey's music player, part of LEVI.

The mix he specified, built as ONE product (2026-09-18 correction):
Bloome (bloome.im, agent-messaging threads) + Metrolist (open-source
YT-music client) MIX AND COMBINE — agent-messaging threads with native
media woven in. Agents curate and play; members share the listening
thread. Not two plays. One.

Media is provider-UNIVERSAL: YouTube is one provider among many behind
a plugin interface. The core never imports a provider SDK.

PROVENANCE (clean-room, L2): no Metrolist code, no Bloome code, no GPLv3
code anywhere in this tree. Recon (~/workspace/recon-report.md,
2026-9-18) studied both targets; every line here is original LEVI-native
work. Metrolist is GPL-3.0 — forking it was never an option.

LAWS:
  L1 provider-universal — core runs against any provider plugin; no
      provider SDK imports in core. Proven by the grep-gate test and by
      the suite running the whole engine against the fake provider.
  L2 clean-room — no GPLv3-derived or target-derived code. Stated here;
      enforced by review, never by accident.
  L3 honest receipts — every play, queue, curation, skip, and thread
      action emits a receipt to the append-only receipt log.
  L4 money 70/30 fail-closed — paid flows split 70 creator / 30
      platform and move ONLY through a Cybrus-marked rail; with no rail
      registered every charge refuses (paper-only).
  L5 thread surface — agent curation/play actions reach a queue ONLY
      through a listening thread's surface; there is no agent-inject
      backdoor on the engine.

STACK (honest wiring — see stack.py for the machine-checked report):
  WIRED (real modules): REIM + RIEM learning loop
      (levi.queta_pan.reim / levi.queta_pan.riem), Echo
      (levi.organs.echo.run_echo), Mandella
      (levi.organs.mandella.run_mandella), Echoverse journey engine
      (levi.echoverse.engine.EchoverseEngine).
  BUILT-HERE: the KFX² four-phase curation method
      (absorb -> reverse -> improve -> return-unreplicable, his words),
      the DemandPulse demand-signal adapter (real recorded signals;
      demandpulse/ ships no score API), and the ten Quetta-Pan
      curator instances (music-domain agents; QuettaPanEngine itself
      is code-domain and is not reused for music).
  MISSING (not faked): real network providers (YouTube et al.),
      real audio rendering/playback on the phone. The engine, queue,
      thread, receipt, and curation layers are proven against
      interfaces and fakes; playback is the open follow-up.

M3U is the universal playlist bridge: any .m3u/.m3u8 imports into a
queue or thread; any queue or thread exports to .m3u.
"""

from __future__ import annotations

__all__ = [
    "providers",
    "m3u",
    "receipts",
    "money",
    "stack",
    "curation",
    "demand",
    "engine",
    "threads",
    "cli",
    "dj",
    "forge",
    "youtube",
]
