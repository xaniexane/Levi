# Stored 2026-09-27 — Buzz Tunes Spotify seam

Removed from `core/levi/buzztunes/` per Chauncey's ruling 2026-09-27:
**"It was supposed to be redone with YouTube not spotify."**

Replaced by `core/levi/buzztunes/youtube.py` (same honest-seam pattern:
`configured()` False until linked, `play()`/`search()` raise
`YouTubeNotConfigured`, no SDK imports in core per law L1).

Kept here under the nothing-thrown-away law — restore if he ever rules
Spotify back in. Git history also holds every version.
