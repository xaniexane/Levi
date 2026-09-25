"""LEVI video learning — analyze any video URL, refine with Chauncey, ingest as knowledge.

Pipeline:  analyze_video(url)      -> VideoPack (description + metadata + transcription)
            export_pack(pack)       -> uploads the pack to Google Drive
            Chauncey refines it      -> in Grok chat / GPT / Claude (his pick, his chat apps)
            download_refined(...)   -> pulls the refined file back from Drive
            ingest_refined(...)     -> validated knowledge entry in days/YYYY-MM-DD.jsonl
            search_video_learn(...) -> ranked keyword search over the corpus

This module is the honest machinery around the human refinement loop.
The full collective-intelligence LAYER is still spec-stage; ingest writes
the corpus that layer will read — it does not fake the layer.

LAWS (law -> guard -> prove; tests/test_video_learn.py checks each):
  1. No transcript without a real engine. A pack's transcript is either
     genuine engine output (transcript_engine names it) or null with
     transcript_status == "blocked" and a blocked_reason. Placeholder
     text, summaries invented as transcripts, and silent omissions are
     all forbidden.
  2. Every pack carries provenance: source_url, fetched_at, fetch_hash
     (sha256 of the EXACT raw bytes fetched), metadata_engine,
     transcript_engine. fetch_hash must equal sha256 of the raw payload.
  3. Ingest accepts only genuinely refined packs: refined_by non-empty,
     origin_pack_hash must match a pack we actually exported (registry
     lookup — no orphaned knowledge), content fields non-empty.
  4. Nothing here pretends to be a model: signal_notes are extractive
     heuristics and say so ("heuristic" provenance). Chat-refinement
     happens in Chauncey's apps, not in this module.

Stdlib-only. External engines (yt-dlp, whisper, vosk) are optional and
detected in engines.py; everything degrades to a clear blocked state.
"""

from __future__ import annotations

__all__ = ["engines", "analyze", "drive_sync", "ingest", "search"]
