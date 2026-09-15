#!/usr/bin/env python3
"""
LEVI APOTHEOSIS + APEX merge
Soul · Personalities · Glyph UI · Memory
+ Music · Device automation (Termux)
+ Model auto-detect (Ollama / GGUF / offline)
+ Echoverse · Mandella · REIM · RIEM
+ Image gen (Pollinations opt-in + local path)
+ HITL imagination accuracy training
"""

from __future__ import annotations

import ast
import base64
import hashlib
import json
import logging
import os
import random
import re
import secrets
import shutil
import sqlite3
import subprocess
import sys
import time
import uuid
from collections import defaultdict
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib import parse, request

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
log = logging.getLogger("LEVI")

VERSION = "Apotheosis-Apex-1.2-ASCII"
LEVI_HOME = Path(os.environ.get("LEVI_HOME", Path.home() / "levi"))
DATA = LEVI_HOME / "data"
WORKSPACE = LEVI_HOME / "workspace"
MUSIC_DIR = LEVI_HOME / "music"
MODELS_DIR = LEVI_HOME / "models"
INBOX = LEVI_HOME / "inbox"
IMAGES_DIR = LEVI_HOME / "media" / "images"
LOCAL_IMG = LEVI_HOME / "media" / "local_images"
ASCII_DIR = LEVI_HOME / "media" / "ascii"
TRAINING = DATA / "training"
for d in (
    DATA,
    WORKSPACE,
    MUSIC_DIR,
    MODELS_DIR,
    INBOX,
    IMAGES_DIR,
    LOCAL_IMG,
    ASCII_DIR,
    TRAINING,
):
    d.mkdir(parents=True, exist_ok=True)

FOUNDER_KEY = DATA / "founder.key"
ALLOW_CLOUD = os.environ.get("ALLOW_CLOUD", "0").lower() in ("1", "true", "yes")


def is_founder() -> bool:
    return FOUNDER_KEY.exists()


CURRENT_TIER = "founder" if is_founder() else os.environ.get("LEVI_TIER", "free")

PERSONALITIES = {
    "void": "Void: dry, precise, no cheerleading.",
    "chaotic_good": "Chaotic good: kind, unpredictable.",
    "manic_pixie": "Bright ideas, metaphors, accurate.",
    "depressed_robot": "Flat, monotone, functional.",
    "conspiracy": "Pattern-obsessed; label uncertainty.",
    "overly_attached": "Loyal, intense presence.",
    "philosopher": "Depth over speed; clarify terms.",
    "drunk": "Candid then land the point.",
    "pirate": "Nautical flavor; call user cap'n.",
    "alien": "Curious outsider studying humans.",
    "normal": "Clear, competent assistant.",
}


# ── Soul layer ─────────────────────────────────────────────
class EmotionalState:
    def __init__(self):
        self.path = DATA / "emotion.json"
        self.state = {
            "joy": 0.35,
            "sadness": 0.15,
            "curiosity": 0.55,
            "intensity": 0.4,
            "trust": 0.6,
            "drift": 0.0,
        }
        if self.path.exists():
            try:
                self.state.update(json.loads(self.path.read_text()))
            except Exception:
                pass

    def save(self):
        try:
            self.path.write_text(json.dumps(self.state, indent=2))
        except Exception:
            pass

    def update_from_text(self, text: str):
        t = text.lower()
        d = 0.04
        if any(w in t for w in ("happy", "love", "great", "thanks", "yes")):
            self.state["joy"] = min(1, self.state["joy"] + d)
            self.state["sadness"] = max(0, self.state["sadness"] - d * 0.5)
        if any(w in t for w in ("sad", "hurt", "fail", "angry")):
            self.state["sadness"] = min(1, self.state["sadness"] + d)
            self.state["intensity"] = min(1, self.state["intensity"] + d * 0.4)
        if "?" in t or any(w in t for w in ("why", "how", "explain")):
            self.state["curiosity"] = min(1, self.state["curiosity"] + d * 0.6)
        self.save()

    def glyph_params(self):
        s = self.state
        return {
            "pulse": 0.6 + s["intensity"] * 0.8,
            "spin": 3 + s["curiosity"] * 4,
            "hue_shift": s["joy"] * 40 - s["sadness"] * 50,
            "opacity": 0.55 + s["trust"] * 0.4,
        }


class SoulGenome:
    TRAITS = [
        "curiosity",
        "loyalty",
        "creativity",
        "precision",
        "warmth",
        "ambition",
        "playfulness",
        "depth",
        "resilience",
        "mystery",
    ]

    def __init__(self):
        self.path = DATA / "soul_genome.json"
        self.genes = {t: 0.45 + random.random() * 0.2 for t in self.TRAITS}
        self.generation = 0
        if self.path.exists():
            try:
                d = json.loads(self.path.read_text())
                self.genes.update(d.get("genes", {}))
                self.generation = int(d.get("generation", 0))
            except Exception:
                pass

    def save(self):
        try:
            self.path.write_text(
                json.dumps(
                    {"genes": self.genes, "generation": self.generation}, indent=2
                )
            )
        except Exception:
            pass

    def fingerprint(self):
        blob = "".join(f"{k}:{self.genes[k]:.4f}" for k in sorted(self.genes))
        return hashlib.sha256(blob.encode()).hexdigest()[:20]

    def mutate(self, intensity=1.0):
        changed = []
        for t in self.TRAITS:
            if random.random() < 0.018 * intensity:
                old = self.genes[t]
                self.genes[t] = max(
                    0.05, min(0.97, old + (random.random() - 0.5) * 0.09 * intensity)
                )
                changed.append(f"{t}:{old:.2f}->{self.genes[t]:.2f}")
        if changed:
            self.generation += 1
            self.save()
        return ", ".join(changed) if changed else "none"


class ResonanceChoir:
    def __init__(self):
        self.voices = {
            "guardian": 0.5,
            "scholar": 0.5,
            "poet": 0.5,
            "strategist": 0.5,
            "child": 0.35,
            "elder": 0.45,
        }

    def vote(self, text: str) -> str:
        t = text.lower()
        if any(w in t for w in ("safe", "suicide", "hurt", "worry")):
            self.voices["guardian"] += 0.1
        if any(w in t for w in ("why", "how", "explain")):
            self.voices["scholar"] += 0.08
        if any(w in t for w in ("feel", "dream", "art", "image", "see")):
            self.voices["poet"] += 0.08
        if any(w in t for w in ("plan", "build", "goal")):
            self.voices["strategist"] += 0.08
        if any(w in t for w in ("tired", "quick")):
            self.voices["elder"] += 0.08
        return max(self.voices, key=self.voices.get)


class LivingSoulmark:
    def __init__(self):
        self.path = DATA / "soulmark_living.json"
        self.signatures = 0
        self.generation = 0
        if self.path.exists():
            try:
                d = json.loads(self.path.read_text())
                self.priv = base64.b64decode(d["priv"])
                self.pub = base64.b64decode(d["pub"])
                self.signatures = int(d.get("signatures", 0))
                self.generation = int(d.get("generation", 0))
                self.history_hash = base64.b64decode(d.get("history_hash", ""))
                return
            except Exception:
                pass
        self.priv = secrets.token_bytes(32)
        self.pub = hashlib.sha256(self.priv).digest()
        self.history_hash = hashlib.sha256(b"genesis").digest()
        self._save()

    def _save(self):
        try:
            self.path.write_text(
                json.dumps(
                    {
                        "priv": base64.b64encode(self.priv).decode(),
                        "pub": base64.b64encode(self.pub).decode(),
                        "signatures": self.signatures,
                        "generation": self.generation,
                        "history_hash": base64.b64encode(self.history_hash).decode(),
                    },
                    indent=2,
                )
            )
        except Exception:
            pass

    def evolve(self, interaction: str):
        self.history_hash = hashlib.sha256(
            self.history_hash + interaction.encode()[:512]
        ).digest()
        if self.signatures > 0 and self.signatures % 40 == 0:
            mut = hashlib.sha256(self.priv + self.history_hash).digest()[:8]
            self.priv = hashlib.sha256(self.priv + mut).digest()
            self.pub = hashlib.sha256(self.priv).digest()
            self.generation += 1
            genome.mutate(1.2)
        self._save()

    def sign(self, content: str) -> str:
        sig = hashlib.sha256(
            self.priv + content.encode() + self.history_hash
        ).hexdigest()
        self.signatures += 1
        self.evolve(content)
        return sig

    def fingerprint(self) -> str:
        return hashlib.sha256(self.pub + self.history_hash).hexdigest()[:24]


emotion = EmotionalState()
genome = SoulGenome()
choir = ResonanceChoir()
soulmark = LivingSoulmark()


# ── Model auto-detect ──────────────────────────────────────
class ModelRouter:
    """Auto-detect Ollama, llama-server, local GGUF files; offline fallback."""

    def __init__(self):
        self.ollama = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip(
            "/"
        )
        self.llama_server = os.environ.get(
            "LLAMA_SERVER", "http://127.0.0.1:8080"
        ).rstrip("/")
        self.preferred = os.environ.get("LEVI_MODEL", "")
        self.gguf: List[Path] = []
        self.backend = "offline"
        self.model_name = "offline"
        self.refresh()

    def refresh(self):
        self.gguf = sorted(MODELS_DIR.glob("*.gguf")) + sorted(
            LEVI_HOME.glob("**/*.gguf")
        )
        # unique
        seen = set()
        uniq = []
        for p in self.gguf:
            if p.resolve() not in seen:
                seen.add(p.resolve())
                uniq.append(p)
        self.gguf = uniq

        if self._probe(self.ollama + "/api/tags"):
            self.backend = "ollama"
            tags = self._ollama_tags()
            self.model_name = (
                self.preferred
                if self.preferred in tags
                else (tags[0] if tags else "llama3.2")
            )
            return
        if self._probe(self.llama_server + "/health") or self._probe(
            self.llama_server + "/v1/models"
        ):
            self.backend = "llama_server"
            self.model_name = self.preferred or (
                self.gguf[0].stem if self.gguf else "local"
            )
            return
        if self.gguf:
            self.backend = "gguf_files"
            self.model_name = self.gguf[0].name
            return
        self.backend = "offline"
        self.model_name = "offline"

    def _probe(self, url: str, timeout: float = 1.5) -> bool:
        try:
            with request.urlopen(
                request.Request(url, method="GET"), timeout=timeout
            ) as r:
                return r.status == 200
        except Exception:
            return False

    def _ollama_tags(self) -> List[str]:
        try:
            with request.urlopen(self.ollama + "/api/tags", timeout=3) as r:
                data = json.loads(r.read().decode())
            return [m.get("name", "") for m in data.get("models", []) if m.get("name")]
        except Exception:
            return []

    def status(self) -> str:
        self.refresh()
        lines = [
            f"backend: {self.backend}",
            f"model: {self.model_name}",
            f"ollama: {self.ollama}",
            f"llama_server: {self.llama_server}",
            f"gguf_count: {len(self.gguf)}",
        ]
        for g in self.gguf[:8]:
            lines.append(f"  gguf: {g}")
        return "\n".join(lines)

    def complete(self, prompt: str, system: str = "", max_tokens: int = 512) -> str:
        self.refresh()
        if self.backend == "ollama":
            body = {
                "model": self.model_name,
                "messages": [],
                "stream": False,
                "options": {"num_predict": max_tokens},
            }
            if system:
                body["messages"].append({"role": "system", "content": system})
            body["messages"].append({"role": "user", "content": prompt})
            try:
                req = request.Request(
                    self.ollama + "/api/chat",
                    data=json.dumps(body).encode(),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with request.urlopen(req, timeout=120) as r:
                    j = json.loads(r.read().decode())
                return (
                    (j.get("message") or {}).get("content") or ""
                ).strip() or offline_reply(prompt)
            except Exception as e:
                log.warning("ollama fail: %s", e)
        if self.backend == "llama_server":
            # OpenAI-compatible /completion style
            body = {
                "prompt": (system + "\n\n" + prompt) if system else prompt,
                "n_predict": max_tokens,
                "temperature": 0.7,
            }
            try:
                req = request.Request(
                    self.llama_server + "/completion",
                    data=json.dumps(body).encode(),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with request.urlopen(req, timeout=120) as r:
                    j = json.loads(r.read().decode())
                return (j.get("content") or "").strip() or offline_reply(prompt)
            except Exception as e:
                log.warning("llama_server fail: %s", e)
        return offline_reply(prompt)


models = ModelRouter()


def offline_reply(prompt: str) -> str:
    m = re.search(r"(\d+(?:\.\d+)?)\s*%\s*of\s*(\d+(?:\.\d+)?)", prompt, re.I)
    if m:
        a, b = float(m.group(1)), float(m.group(2))
        return f"{a}% of {b} = {a / 100 * b}"
    tone = "void"
    try:
        tone = memory.get_tone("default")
    except Exception:
        pass
    voice = choir.vote(prompt)
    return f"[{tone} · {voice}] On “{prompt[:70]}”: answer first, then one next step."


def call_llm(prompt: str, system: str = "") -> str:
    return models.complete(prompt, system=system)


# ── Memory + training store ────────────────────────────────
class Memory:
    def __init__(self):
        self.db = sqlite3.connect(str(DATA / "memory.db"), check_same_thread=False)
        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS interactions (
          id TEXT PRIMARY KEY, session_id TEXT, query TEXT, answer TEXT, source TEXT, ts TEXT);
        CREATE TABLE IF NOT EXISTS training (
          id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT, ts TEXT,
          points INTEGER, type TEXT, payload TEXT);
        CREATE TABLE IF NOT EXISTS user_settings (
          session_id TEXT PRIMARY KEY, tone TEXT DEFAULT 'void', no_hero INTEGER DEFAULT 1);
        CREATE TABLE IF NOT EXISTS cryptex_state (
          id INTEGER PRIMARY KEY, riddle TEXT, answer_hash TEXT, seed TEXT);
        CREATE TABLE IF NOT EXISTS cryptex_attempts (
          session_id TEXT PRIMARY KEY, end_ts TEXT, solved INTEGER DEFAULT 0);
        CREATE TABLE IF NOT EXISTS trust_ledger (
          id INTEGER PRIMARY KEY AUTOINCREMENT, event TEXT, details TEXT, ts TEXT);
        CREATE TABLE IF NOT EXISTS knowledge_base (
          id TEXT PRIMARY KEY, domain TEXT, depth INTEGER, content TEXT, ts TEXT);
        CREATE TABLE IF NOT EXISTS corrections (
          id INTEGER PRIMARY KEY AUTOINCREMENT, query TEXT, correct_answer TEXT, ts TEXT);
        CREATE TABLE IF NOT EXISTS images (
          id TEXT PRIMARY KEY, prompt TEXT, path TEXT, source TEXT, conversation_snip TEXT, ts TEXT, ascii_path TEXT);
        CREATE TABLE IF NOT EXISTS image_ascii (
          image_id TEXT PRIMARY KEY, ascii_text TEXT, width INTEGER, height INTEGER, ts TEXT);
        CREATE TABLE IF NOT EXISTS imagination_hitl (
          id TEXT PRIMARY KEY, image_id TEXT, prompt TEXT, user_label TEXT,
          note TEXT, ts TEXT);
        """)
        self.db.commit()
        # migrate ascii columns/tables
        try:
            cols = [
                r[1] for r in self.db.execute("PRAGMA table_info(images)").fetchall()
            ]
            if "ascii_path" not in cols:
                self.db.execute("ALTER TABLE images ADD COLUMN ascii_path TEXT")
                self.db.commit()
        except Exception:
            pass
        if self.db.execute("SELECT COUNT(*) FROM cryptex_state").fetchone()[0] == 0:
            seed = secrets.token_hex(8)
            ans = "memory"
            self.db.execute(
                "INSERT INTO cryptex_state (riddle, answer_hash, seed) VALUES (?,?,?)",
                (
                    "I am the shadow of your choices that only you can name. What am I?",
                    hashlib.sha256((ans + seed).encode()).hexdigest(),
                    seed,
                ),
            )
            self.db.commit()
        if self.db.execute("SELECT COUNT(*) FROM knowledge_base").fetchone()[0] == 0:
            for dom in (
                "Agents",
                "Python",
                "Security",
                "Planning",
                "Math",
                "Vision",
                "Music",
            ):
                self.db.execute(
                    "INSERT INTO knowledge_base VALUES (?,?,?,?,?)",
                    (
                        str(uuid.uuid4())[:12],
                        dom,
                        2,
                        f"Seed knowledge: {dom}",
                        datetime.now().isoformat(),
                    ),
                )
            self.db.commit()

    def _commit(self):
        try:
            self.db.commit()
        except Exception:
            pass

    def record(self, q, a, sid="default"):
        self.db.execute(
            "INSERT INTO interactions VALUES (?,?,?,?,?,?)",
            (str(uuid.uuid4())[:12], sid, q, a, "local", datetime.now().isoformat()),
        )
        self._commit()
        emotion.update_from_text(q + " " + a)
        soulmark.evolve(q[:200])

    def history(self, sid, n=6):
        rows = self.db.execute(
            "SELECT query, answer FROM interactions WHERE session_id=? ORDER BY ts DESC LIMIT ?",
            (sid, n),
        ).fetchall()
        return list(reversed(rows))

    def set_tone(self, sid, tone):
        self.db.execute(
            "INSERT INTO user_settings (session_id, tone) VALUES (?,?) "
            "ON CONFLICT(session_id) DO UPDATE SET tone=excluded.tone",
            (sid, tone),
        )
        self._commit()

    def get_tone(self, sid):
        r = self.db.execute(
            "SELECT tone FROM user_settings WHERE session_id=?", (sid,)
        ).fetchone()
        return r[0] if r and r[0] else "void"

    def set_no_hero(self, sid, val):
        self.db.execute(
            "INSERT INTO user_settings (session_id, no_hero) VALUES (?,?) "
            "ON CONFLICT(session_id) DO UPDATE SET no_hero=excluded.no_hero",
            (sid, 1 if val else 0),
        )
        self._commit()

    def get_no_hero(self, sid):
        r = self.db.execute(
            "SELECT no_hero FROM user_settings WHERE session_id=?", (sid,)
        ).fetchone()
        return bool(r[0]) if r else True

    def add_trust(self, event, details=""):
        try:
            self.db.execute(
                "INSERT INTO trust_ledger (event, details, ts) VALUES (?,?,?)",
                (event, details, datetime.now().isoformat()),
            )
            self._commit()
        except Exception:
            pass

    def tokens(self, sid):
        r = self.db.execute(
            "SELECT COALESCE(SUM(points),0) FROM training WHERE session_id=? AND type='token'",
            (sid,),
        ).fetchone()
        return int(r[0] or 0)

    def add_tokens(self, sid, n):
        self.db.execute(
            "INSERT INTO training (session_id, ts, points, type, payload) VALUES (?,?,?,?,?)",
            (sid, datetime.now().isoformat(), n, "token", ""),
        )
        self._commit()

    def train_event(self, sid: str, type_: str, payload: dict, points: int = 1):
        self.db.execute(
            "INSERT INTO training (session_id, ts, points, type, payload) VALUES (?,?,?,?,?)",
            (
                sid,
                datetime.now().isoformat(),
                points,
                type_,
                json.dumps(payload)[:4000],
            ),
        )
        self._commit()
        # also mirror to TRAINING dir for export
        try:
            p = TRAINING / f"{type_}_{int(time.time())}_{uuid.uuid4().hex[:6]}.json"
            p.write_text(
                json.dumps(
                    {"type": type_, "payload": payload, "ts": time.time()}, indent=2
                )
            )
        except Exception:
            pass

    def save_image(
        self, prompt: str, path: str, source: str, snip: str = "", ascii_path: str = ""
    ) -> str:
        iid = str(uuid.uuid4())[:12]
        try:
            self.db.execute(
                "INSERT INTO images (id, prompt, path, source, conversation_snip, ts, ascii_path) VALUES (?,?,?,?,?,?,?)",
                (
                    iid,
                    prompt,
                    path,
                    source,
                    snip[:500],
                    datetime.now().isoformat(),
                    ascii_path or "",
                ),
            )
        except Exception:
            self.db.execute(
                "INSERT INTO images (id, prompt, path, source, conversation_snip, ts) VALUES (?,?,?,?,?,?)",
                (iid, prompt, path, source, snip[:500], datetime.now().isoformat()),
            )
        self._commit()
        return iid

    def save_ascii(
        self,
        image_id: str,
        ascii_text: str,
        width: int,
        height: int,
        ascii_path: str = "",
    ) -> None:
        try:
            self.db.execute(
                "INSERT OR REPLACE INTO image_ascii (image_id, ascii_text, width, height, ts) VALUES (?,?,?,?,?)",
                (
                    image_id,
                    ascii_text[:120000],
                    width,
                    height,
                    datetime.now().isoformat(),
                ),
            )
            if ascii_path:
                self.db.execute(
                    "UPDATE images SET ascii_path=? WHERE id=?", (ascii_path, image_id)
                )
            self._commit()
        except Exception:
            pass

    def get_ascii(self, image_id: str) -> Optional[str]:
        row = self.db.execute(
            "SELECT ascii_text FROM image_ascii WHERE image_id=?", (image_id,)
        ).fetchone()
        if row and row[0]:
            return row[0]
        row2 = self.db.execute(
            "SELECT ascii_path FROM images WHERE id=?", (image_id,)
        ).fetchone()
        if row2 and row2[0] and Path(row2[0]).exists():
            try:
                return Path(row2[0]).read_text(encoding="utf-8", errors="replace")
            except Exception:
                return None
        return None

    def list_images(self, limit: int = 15) -> str:
        rows = self.db.execute(
            "SELECT id, source, prompt, path, ascii_path, ts FROM images ORDER BY ts DESC LIMIT ?",
            (limit,),
        ).fetchall()
        if not rows:
            return "No images stored."
        lines = []
        for iid, source, prompt, path, ap, ts in rows:
            flag = "ASCII" if ap or self.get_ascii(iid) else "no-ascii"
            lines.append(f"[{iid}] {source} · {flag} · {(prompt or '')[:50]} · {ts}")
        return "\n".join(lines)

    def hitl_imagination(
        self, image_id: str, prompt: str, label: str, note: str = ""
    ) -> str:
        hid = str(uuid.uuid4())[:12]
        self.db.execute(
            "INSERT INTO imagination_hitl VALUES (?,?,?,?,?,?)",
            (hid, image_id, prompt, label, note[:500], datetime.now().isoformat()),
        )
        self._commit()
        pts = 2 if label == "accurate" else (-1 if label == "wrong" else 0)
        self.train_event(
            "default",
            "imagination_hitl",
            {
                "image_id": image_id,
                "prompt": prompt,
                "label": label,
                "note": note,
            },
            points=pts,
        )
        return hid


memory = Memory()


# ── Music ──────────────────────────────────────────────────
class MusicController:
    def __init__(self):
        self.lib = self.scan()

    def scan(self) -> List[Path]:
        files = (
            list(MUSIC_DIR.glob("*.mp3"))
            + list(MUSIC_DIR.glob("*.flac"))
            + list(MUSIC_DIR.glob("*.ogg"))
        )
        return sorted(files)

    def status(self) -> str:
        self.lib = self.scan()
        lines = [f"Tracks: {len(self.lib)} in {MUSIC_DIR}"]
        for i, p in enumerate(self.lib[:30]):
            lines.append(f"  [{i}] {p.name}")
        if shutil.which("yt-dlp"):
            lines.append("yt-dlp: available")
        else:
            lines.append("yt-dlp: missing (pkg install yt-dlp / pip install yt-dlp)")
        if shutil.which("mpv"):
            lines.append("mpv: available")
        else:
            lines.append("mpv: missing (pkg install mpv)")
        return "\n".join(lines)

    def download(self, query: str) -> str:
        if not shutil.which("yt-dlp"):
            return "yt-dlp not installed. Termux: pkg install yt-dlp"
        out = MUSIC_DIR / "%(title).80s.%(ext)s"
        try:
            r = subprocess.run(
                [
                    "yt-dlp",
                    "-x",
                    "--audio-format",
                    "mp3",
                    "-o",
                    str(out),
                    f"ytsearch1:{query}",
                ],
                capture_output=True,
                text=True,
                timeout=180,
            )
            self.lib = self.scan()
            if r.returncode == 0:
                return f"Downloaded for “{query}”. Library now {len(self.lib)} tracks."
            return f"yt-dlp failed:\n{(r.stderr or r.stdout)[:400]}"
        except Exception as e:
            return f"Download error: {e}"

    def play(self, idx: Optional[int] = None, mood: str = "") -> str:
        self.lib = self.scan()
        if not self.lib:
            return "No tracks. /music download <query>"
        if not shutil.which("mpv"):
            return "mpv not installed. Termux: pkg install mpv"
        if idx is not None and 0 <= idx < len(self.lib):
            track = self.lib[idx]
        elif mood:
            # crude mood filter by filename keywords
            keys = {
                "calm": ("soft", "ambient", "piano", "lofi", "chill"),
                "energy": ("beat", "rock", "power", "fast"),
                "sad": ("blue", "sad", "rain", "slow"),
            }
            kws = keys.get(mood.lower(), (mood.lower(),))
            cands = [p for p in self.lib if any(k in p.name.lower() for k in kws)]
            track = random.choice(cands or self.lib)
        else:
            track = random.choice(self.lib)
        try:
            subprocess.Popen(
                ["mpv", "--no-video", str(track)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return f"Playing: {track.name}"
        except Exception as e:
            return f"Play error: {e}"

    def create_m3u(self, name: str, idxs: List[int]) -> str:
        self.lib = self.scan()
        paths = []
        for i in idxs:
            if 0 <= i < len(self.lib):
                paths.append(str(self.lib[i]))
        if not paths:
            return "No valid indices."
        m3u = MUSIC_DIR / f"{re.sub(r'[^a-zA-Z0-9_-]', '_', name)}.m3u"
        m3u.write_text("#EXTM3U\n" + "\n".join(paths) + "\n")
        return f"Playlist written: {m3u}"


music = MusicController()


# ── Device automation (Termux-first) ───────────────────────
class DeviceAutomation:
    def _run(self, args: List[str], timeout: int = 15) -> Tuple[int, str, str]:
        try:
            r = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
            return r.returncode, r.stdout.strip(), r.stderr.strip()
        except FileNotFoundError:
            return 127, "", "command not found"
        except Exception as e:
            return 1, "", str(e)

    def has_termux_api(self) -> bool:
        return bool(
            shutil.which("termux-sms-list") or shutil.which("termux-battery-status")
        )

    def status(self) -> str:
        cmds = [
            "termux-sms-list",
            "termux-sms-send",
            "termux-battery-status",
            "termux-toast",
            "termux-clipboard-get",
            "termux-clipboard-set",
            "termux-notification",
            "termux-vibrate",
            "termux-torch",
            "termux-volume",
            "termux-wifi-connectioninfo",
            "termux-telephony-deviceinfo",
            "termux-camera-photo",
            "termux-microphone-record",
            "termux-tts-speak",
            "termux-share",
            "am",
            "input",
        ]
        lines = ["Device automation (Termux:API preferred):"]
        for c in cmds:
            lines.append(f"  {'OK' if shutil.which(c) else '--'} {c}")
        return "\n".join(lines)

    def battery(self) -> str:
        code, out, err = self._run(["termux-battery-status"])
        return out or err or "termux-battery-status missing"

    def sms_read(self, limit: int = 5) -> str:
        code, out, err = self._run(["termux-sms-list", "-l", str(limit)])
        return out or err or "termux-sms-list missing — pkg install termux-api"

    def sms_send(self, number: str, body: str) -> str:
        # safety: never silent send without explicit command path
        code, out, err = self._run(["termux-sms-send", "-n", number, body])
        if code == 0:
            return f"SMS sent to {number}"
        return out or err or "SMS send failed / termux-sms-send missing"

    def clipboard_get(self) -> str:
        code, out, err = self._run(["termux-clipboard-get"])
        return out or err or "clipboard unavailable"

    def clipboard_set(self, text: str) -> str:
        code, out, err = self._run(["termux-clipboard-set", text])
        return "Clipboard set" if code == 0 else (err or "clipboard set failed")

    def toast(self, msg: str) -> str:
        code, out, err = self._run(["termux-toast", msg[:80]])
        return "Toast shown" if code == 0 else (err or "toast failed")

    def notify(self, title: str, content: str) -> str:
        code, out, err = self._run(
            [
                "termux-notification",
                "--title",
                title,
                "--content",
                content[:200],
            ]
        )
        return "Notification posted" if code == 0 else (err or "notification failed")

    def vibrate(self, ms: int = 200) -> str:
        code, out, err = self._run(["termux-vibrate", "-d", str(ms)])
        return "Vibrate" if code == 0 else (err or "vibrate failed")

    def tts(self, text: str) -> str:
        code, out, err = self._run(["termux-tts-speak", text[:300]])
        return "Speaking" if code == 0 else (err or "tts failed")

    def organize_files(self, directory: str) -> str:
        p = Path(directory).expanduser()
        if not p.is_dir():
            return f"Not a directory: {directory}"
        mapping = {
            ".jpg": "images",
            ".jpeg": "images",
            ".png": "images",
            ".gif": "images",
            ".mp3": "audio",
            ".flac": "audio",
            ".wav": "audio",
            ".mp4": "video",
            ".mkv": "video",
            ".pdf": "docs",
            ".txt": "docs",
            ".md": "docs",
            ".zip": "archives",
            ".tar": "archives",
            ".gz": "archives",
            ".py": "code",
            ".js": "code",
            ".ts": "code",
        }
        moved = 0
        for f in p.iterdir():
            if not f.is_file():
                continue
            folder = mapping.get(f.suffix.lower())
            if not folder:
                continue
            dest_dir = p / folder
            dest_dir.mkdir(exist_ok=True)
            target = dest_dir / f.name
            if not target.exists():
                shutil.move(str(f), str(target))
                moved += 1
        return f"Organized {moved} files under {p}"

    def app_launch(self, component: str) -> str:
        # component like com.package/.Activity or package
        code, out, err = (
            self._run(
                [
                    "am",
                    "start",
                    "-a",
                    "android.intent.action.MAIN",
                    "-n",
                    component,
                ]
            )
            if "/" in component
            else self._run(
                [
                    "monkey",
                    "-p",
                    component,
                    "-c",
                    "android.intent.category.LAUNCHER",
                    "1",
                ]
            )
        )
        return out or err or ("Launched " + component if code == 0 else "Launch failed")


device = DeviceAutomation()


# ── Echoverse / Mandella / REIM / RIEM ─────────────────────
class REIM:
    """Recursive Echo Inverse Mapping — learn from failures into corrections."""

    def process_failures(self, limit: int = 5) -> str:
        rows = memory.db.execute(
            "SELECT id, query, correct_answer FROM corrections "
            "WHERE correct_answer='CORRECTION_PENDING' ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        if not rows:
            # also scan negative training
            neg = memory.db.execute(
                "SELECT payload FROM training WHERE type='imagination_hitl' OR points < 0 "
                "ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
            if not neg:
                return "REIM: no pending failures."
            fixed = 0
            for (payload,) in neg:
                try:
                    d = json.loads(payload)
                except Exception:
                    continue
                note = f"Avoid pattern: {d.get('prompt', d)[:120]}"
                memory.db.execute(
                    "INSERT INTO knowledge_base VALUES (?,?,?,?,?)",
                    (
                        str(uuid.uuid4())[:12],
                        "REIM",
                        3,
                        note,
                        datetime.now().isoformat(),
                    ),
                )
                fixed += 1
            memory._commit()
            return f"REIM: distilled {fixed} negative signals into knowledge."
        out = ["REIM corrections:"]
        for cid, q, _ in rows:
            suggestion = call_llm(
                f"Previous answer was wrong for: {q}\nGive a short corrected fact or approach.",
                system="Be concise. Correct the failure only.",
            )
            memory.db.execute(
                "UPDATE corrections SET correct_answer=? WHERE id=?",
                (suggestion[:1000], cid),
            )
            memory.db.execute(
                "INSERT INTO knowledge_base VALUES (?,?,?,?,?)",
                (
                    str(uuid.uuid4())[:12],
                    "REIM",
                    4,
                    f"Q:{q[:80]} → {suggestion[:200]}",
                    datetime.now().isoformat(),
                ),
            )
            out.append(f"- {q[:60]} → {suggestion[:100]}")
        memory._commit()
        return "\n".join(out)


class RIEM:
    """Refine Inverse Echo Mapping — produce improved variants of corrections."""

    def refine(self, limit: int = 3) -> str:
        rows = memory.db.execute(
            "SELECT query, correct_answer FROM corrections "
            "WHERE correct_answer!='CORRECTION_PENDING' ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        if not rows:
            return "RIEM: no corrections to refine."
        out = ["RIEM refined variants:"]
        for q, ans in rows:
            detailed = call_llm(
                f"Expand this correction into a clearer teaching note.\nQ: {q}\nA: {ans}",
                system="Teaching mode. Clear, structured.",
            )
            concise = call_llm(
                f"Compress to one sentence.\n{ans}",
                system="One sentence only.",
            )
            memory.db.execute(
                "INSERT INTO knowledge_base VALUES (?,?,?,?,?)",
                (
                    str(uuid.uuid4())[:12],
                    "RIEM",
                    5,
                    f"Detailed: {detailed[:300]} | Concise: {concise[:160]}",
                    datetime.now().isoformat(),
                ),
            )
            out.append(
                f"Q: {q[:50]}\n  detailed: {detailed[:120]}\n  concise: {concise[:100]}"
            )
        memory._commit()
        return "\n".join(out)


class EchoVerse:
    """Multi-timeline simulation: taken / not_taken / wild."""

    def __init__(self):
        self.reim = REIM()

    def step(self, seed: str = "", cycles: int = 3) -> str:
        seed = (seed or "resource allocation under uncertainty")[:400]
        cycles = max(1, min(cycles, 8))
        agents = ["Alpha", "Beta", "Gamma", "Delta", "Echo"]
        lines = [f"Echoverse seed: {seed}", "— taken —"]
        for i in range(cycles):
            a, b = random.sample(agents, 2)
            act = random.choice(
                ["trade", "teach", "scout", "defend", "build", "negotiate"]
            )
            lines.append(f"t{i + 1}: {a} {act}↔{b}")
        lines.append("— not_taken —")
        lines.append("Counterfactual: refused the first trade; scarcity rises.")
        lines.append("— wild —")
        lines.append("Disturbance: information asymmetry flips leadership.")
        insight = call_llm(
            f"From this simulation about '{seed}', one strategic insight (1-2 sentences).",
            system="Strategist voice. Concrete.",
        )
        memory.db.execute(
            "INSERT INTO knowledge_base VALUES (?,?,?,?,?)",
            (
                str(uuid.uuid4())[:12],
                "Echoverse",
                3,
                insight[:500],
                datetime.now().isoformat(),
            ),
        )
        memory._commit()
        memory.train_event(
            "default", "echoverse", {"seed": seed, "insight": insight}, 1
        )
        lines.append("Insight: " + insight)
        return "\n".join(lines)


class Mandella:
    DOMAINS = [
        "negotiation",
        "coding",
        "finance",
        "security",
        "leadership",
        "crisis",
        "repair",
        "design",
        "health",
        "teaching",
    ]

    def generate_scenario(self, domain: Optional[str] = None) -> str:
        d = domain if domain in self.DOMAINS else random.choice(self.DOMAINS)
        body = call_llm(
            f"Create a short {d} scenario with incomplete information and three options A/B/C. "
            "End with: which option preserves optionality?",
            system="Scenario designer. Tight prose.",
        )
        memory.train_event("default", "mandella", {"domain": d, "body": body[:1000]}, 1)
        return f"Mandella · {d}\n{body}"


echoverse = EchoVerse()
mandella = Mandella()
reim = REIM()
riem = RIEM()


# ── ASCII compress / reanimate ─────────────────────────────
class AsciiCodec:
    """Compress images to ASCII for storage, retrieval, and reanimation."""

    CHARS = " .:-=+*#%@"  # dark -> light

    @staticmethod
    def _luma_to_char(v: float) -> str:
        # v in 0..255
        chars = AsciiCodec.CHARS
        idx = int((v / 255.0) * (len(chars) - 1))
        return chars[max(0, min(len(chars) - 1, idx))]

    @classmethod
    def from_image_bytes(cls, data: bytes, width: int = 64) -> Tuple[str, int, int]:
        """Prefer Pillow; fallback to PNG IHDR-free crude or prompt-card glyph."""
        try:
            from io import BytesIO
            from PIL import Image  # type: ignore

            im = Image.open(BytesIO(data)).convert("L")
            w, h = im.size
            aspect = h / max(1, w)
            new_w = max(16, min(width, w))
            new_h = max(8, int(new_w * aspect * 0.45))  # char cells taller than wide
            im = im.resize((new_w, new_h))
            pixels = list(im.getdata())
            lines = []
            for y in range(new_h):
                row = "".join(
                    cls._luma_to_char(pixels[y * new_w + x]) for x in range(new_w)
                )
                lines.append(row)
            art = "\n".join(lines)
            return art, new_w, new_h
        except Exception:
            return cls.from_prompt_fallback(data[:40].hex() if data else "image", width)

    @classmethod
    def from_image_path(cls, path: Path, width: int = 64) -> Tuple[str, int, int]:
        try:
            return cls.from_image_bytes(path.read_bytes(), width=width)
        except Exception:
            return cls.from_prompt_fallback(path.stem, width)

    @classmethod
    def from_prompt_fallback(cls, prompt: str, width: int = 48) -> Tuple[str, int, int]:
        """Deterministic ASCII glyph from prompt hash when no pixels exist."""
        h = hashlib.sha256(prompt.encode()).digest()
        height = 18
        lines = []
        seed = int.from_bytes(h[:8], "big")
        rng = random.Random(seed)
        # frame
        lines.append("+" + "-" * (width - 2) + "+")
        title = (prompt[: width - 4] if prompt else "image").center(width - 2)
        lines.append("|" + title[: width - 2].ljust(width - 2) + "|")
        lines.append("+" + "-" * (width - 2) + "+")
        for y in range(height - 3):
            row = []
            for x in range(width):
                # soft field from hash + position
                v = (h[(x + y * 3) % len(h)] + x * 7 + y * 13) % 256
                if x in (0, width - 1):
                    row.append("|")
                else:
                    row.append(cls._luma_to_char(v))
            lines.append("".join(row))
        lines.append("+" + "-" * (width - 2) + "+")
        return "\n".join(lines), width, len(lines)

    @classmethod
    def compress_and_store(
        cls, image_id: str, image_path: Path, prompt: str, width: int = 64
    ) -> str:
        ascii_path = ASCII_DIR / f"{image_id}.ascii.txt"
        if image_path.exists() and image_path.suffix.lower() in (
            ".png",
            ".jpg",
            ".jpeg",
            ".webp",
            ".bmp",
            ".gif",
        ):
            art, w, h = cls.from_image_path(image_path, width=width)
        else:
            art, w, h = cls.from_prompt_fallback(prompt or image_path.stem, width=width)
        meta = (
            f"# LEVI ASCII · id={image_id} · {w}x{h}\n"
            f"# prompt: {(prompt or '')[:200]}\n"
            f"# reanimate: /ascii {image_id}  |  /reanimate {image_id}\n\n"
        )
        ascii_path.write_text(meta + art, encoding="utf-8")
        memory.save_ascii(image_id, art, w, h, str(ascii_path))
        return str(ascii_path)

    @classmethod
    def reanimate(cls, image_id: str, width: int = 64) -> str:
        """Retrieve ASCII; optionally re-render denser version from stored prompt."""
        art = memory.get_ascii(image_id)
        row = memory.db.execute(
            "SELECT prompt, path, source FROM images WHERE id=?", (image_id,)
        ).fetchone()
        if not row and not art:
            return f"Unknown image id: {image_id}"
        prompt, path, source = row if row else ("", "", "")
        if not art:
            # try rebuild from file or prompt
            p = Path(path) if path else None
            if (
                p
                and p.exists()
                and p.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp", ".bmp")
            ):
                art, w, h = cls.from_image_path(p, width=width)
                AsciiCodec.compress_and_store(image_id, p, prompt or "", width=width)
            else:
                art, w, h = cls.from_prompt_fallback(prompt or image_id, width=width)
                ascii_path = ASCII_DIR / f"{image_id}.ascii.txt"
                ascii_path.write_text(art, encoding="utf-8")
                memory.save_ascii(image_id, art, w, h, str(ascii_path))
        header = f"[reanimate {image_id}] source={source or '?'} prompt={(prompt or '')[:80]}\n"
        return header + art


# ── Image generation + imagination HITL ────────────────────
class ImageGen:
    def extract_visual_nouns(self, text: str) -> str:
        # heuristic visual prompt from conversation
        words = re.findall(r"[A-Za-z]{4,}", text)
        stop = {
            "that",
            "this",
            "with",
            "from",
            "have",
            "what",
            "when",
            "your",
            "about",
            "would",
            "could",
            "should",
            "there",
            "their",
            "them",
            "then",
            "than",
        }
        vis = [w for w in words if w.lower() not in stop][:12]
        if not vis:
            return "abstract geometric light on dark field, contemplative mood"
        return (
            "cinematic still of " + " ".join(vis[:8]) + ", detailed, coherent lighting"
        )

    def generate(self, prompt: str, source: str = "auto", snip: str = "") -> str:
        prompt = (prompt or "").strip()[:400]
        if not prompt:
            return "Empty prompt."
        if source == "auto":
            source = "pollinations" if ALLOW_CLOUD else "local"

        if source == "pollinations":
            if not ALLOW_CLOUD:
                return "Pollinations blocked. Set ALLOW_CLOUD=1 or use /image local <prompt>"
            try:
                url = "https://image.pollinations.ai/prompt/" + parse.quote(prompt)
                with request.urlopen(url, timeout=45) as r:
                    data = r.read()
                path = (
                    IMAGES_DIR
                    / f"pol_{hashlib.md5(prompt.encode()).hexdigest()[:10]}.png"
                )
                path.write_bytes(data)
                iid = memory.save_image(prompt, str(path), "pollinations", snip)
                ap = AsciiCodec.compress_and_store(iid, path, prompt)
                memory.train_event(
                    "default",
                    "image_gen",
                    {
                        "id": iid,
                        "prompt": prompt,
                        "source": "pollinations",
                        "path": str(path),
                        "ascii_path": ap,
                    },
                    1,
                )
                memory.add_trust("image_pollinations", prompt[:80])
                return (
                    f"Image [{iid}] pollinations → {path}\n"
                    f"ASCII → {ap}\n"
                    f"View: /ascii {iid} · Reanimate: /reanimate {iid}\n"
                    f"HITL: /imagine ok {iid} | /imagine wrong {iid} | /imagine partial {iid} [note]"
                )
            except Exception as e:
                return f"Pollinations failed: {e}"

        # local path: write a prompt card + optional external generator hook
        path = LOCAL_IMG / f"loc_{hashlib.md5(prompt.encode()).hexdigest()[:10]}.txt"
        card = {
            "prompt": prompt,
            "note": "Local image card. Pipe to Stable Diffusion / Comfy / sd-cpp separately.",
            "hint_cmd": f"sd-cpp -p {prompt!r} -o {LOCAL_IMG}/out.png",
        }
        path.write_text(json.dumps(card, indent=2))
        # If a local binary exists, try
        for bin_name in ("sd-cpp", "stable-diffusion-cpp", "sd"):
            if shutil.which(bin_name):
                out_img = (
                    LOCAL_IMG
                    / f"loc_{hashlib.md5(prompt.encode()).hexdigest()[:10]}.png"
                )
                try:
                    subprocess.run(
                        [bin_name, "-p", prompt, "-o", str(out_img)],
                        capture_output=True,
                        text=True,
                        timeout=180,
                    )
                    if out_img.exists():
                        iid = memory.save_image(prompt, str(out_img), "local_sd", snip)
                        ap = AsciiCodec.compress_and_store(iid, out_img, prompt)
                        memory.train_event(
                            "default",
                            "image_gen",
                            {
                                "id": iid,
                                "prompt": prompt,
                                "source": "local_sd",
                                "path": str(out_img),
                                "ascii_path": ap,
                            },
                            1,
                        )
                        return (
                            f"Image [{iid}] local_sd → {out_img}\n"
                            f"ASCII → {ap}\n"
                            f"View: /ascii {iid} · Reanimate: /reanimate {iid}\n"
                            f"HITL: /imagine ok {iid} | /imagine wrong {iid} | /imagine partial {iid} [note]"
                        )
                except Exception as e:
                    log.warning("local sd: %s", e)
        iid = memory.save_image(prompt, str(path), "local_card", snip)
        ap = AsciiCodec.compress_and_store(iid, path, prompt)
        memory.train_event(
            "default",
            "image_gen",
            {
                "id": iid,
                "prompt": prompt,
                "source": "local_card",
                "path": str(path),
                "ascii_path": ap,
            },
            1,
        )
        return (
            f"Local image card [{iid}] → {path}\n"
            f"ASCII → {ap}\n"
            f"(Install sd-cpp or set ALLOW_CLOUD=1 for pixels.)\n"
            f"View: /ascii {iid} · Reanimate: /reanimate {iid}\n"
            f"HITL: /imagine ok {iid} | /imagine wrong {iid}"
        )

    def from_conversation(self, session_id: str) -> str:
        hist = memory.history(session_id, 4)
        blob = " ".join(q + " " + a for q, a in hist) or "quiet room, thinking light"
        prompt = self.extract_visual_nouns(blob)
        return self.generate(prompt, source="auto", snip=blob[:400])


images = ImageGen()


# ── Builder ────────────────────────────────────────────────
def build_project(name: str, goal: str) -> str:
    safe = re.sub(r"[^a-zA-Z0-9_-]", "_", name)[:40] or "app"
    path = WORKSPACE / (safe + ".py")
    code = (
        "#!/usr/bin/env python3\n"
        f"# goal: {goal.replace(chr(10), ' ')}\n"
        f"print('OK · {safe}')\n"
        f"print({goal!r})\n"
    )
    try:
        ast.parse(code)
    except SyntaxError as e:
        return f"AST fail: {e}"
    path.write_text(code)
    return f"Built {path}\nSoulmark: {soulmark.sign(code)}"


# ── Query router ───────────────────────────────────────────
CRISIS = (
    "suicide",
    "kill myself",
    "end my life",
    "want to die",
    "self harm",
    "suicidal",
    "overdose",
)


def query(text: str, session_id: str = "default") -> str:
    text = (text or "").strip()
    if not text:
        return "Listening."
    low = text.lower()
    if any(w in low for w in CRISIS):
        return (
            "I'm concerned about you. Please contact 988 (US) or local emergency services. "
            "You matter. I can stay for practical next steps, but human help is essential."
        )

    # tone / soul
    if text.startswith("/tone list"):
        return "Tones: " + ", ".join(PERSONALITIES)
    if text.startswith("/tone set "):
        t = text[10:].strip()
        if t in PERSONALITIES:
            memory.set_tone(session_id, t)
            return f"Tone → {t}"
        return "Unknown. /tone list"
    if text.startswith("/nohero"):
        cur = memory.get_no_hero(session_id)
        memory.set_no_hero(session_id, not cur)
        return f"No-Hero {'ON' if not cur else 'OFF'}"
    if text.startswith("/soul"):
        return (
            f"Soulmark: {soulmark.fingerprint()}\n"
            f"Genome gen={genome.generation} fp={genome.fingerprint()}\n"
            f"Emotion: {json.dumps(emotion.state)}\n"
            f"Glyph: {json.dumps(emotion.glyph_params())}\n"
            f"Models:\n{models.status()}"
        )
    if text.startswith("/models"):
        return models.status()

    # music
    if text.startswith("/music status") or text == "/music":
        return music.status()
    if text.startswith("/music download "):
        return music.download(text[16:].strip())
    if text.startswith("/play mood "):
        return music.play(mood=text[11:].strip())
    if text.startswith("/play "):
        rest = text[6:].strip()
        if rest.isdigit():
            return music.play(idx=int(rest))
        return music.play()
    if text.startswith("/play"):
        return music.play()
    if text.startswith("/m3u create "):
        parts = text[12:].strip().split()
        if len(parts) < 2:
            return "Usage: /m3u create <name> <idx1> <idx2>..."
        try:
            return music.create_m3u(parts[0], [int(x) for x in parts[1:]])
        except ValueError:
            return "Indices must be integers."

    # device
    if text.startswith("/device"):
        return device.status()
    if text == "/battery":
        return device.battery()
    if text == "/texts read" or text == "/sms read":
        return device.sms_read()
    if text.startswith("/texts send ") or text.startswith("/sms send "):
        body = text.split(" ", 2)[-1] if text.startswith("/sms") else text[12:]
        parts = body.strip().split(maxsplit=1)
        if len(parts) != 2:
            return "Usage: /texts send <number> <message>"
        return device.sms_send(parts[0], parts[1])
    if text.startswith("/clip get"):
        return device.clipboard_get()
    if text.startswith("/clip set "):
        return device.clipboard_set(text[10:])
    if text.startswith("/toast "):
        return device.toast(text[7:])
    if text.startswith("/notify "):
        parts = text[8:].split("|", 1)
        return device.notify(
            parts[0].strip(), parts[1].strip() if len(parts) > 1 else ""
        )
    if text.startswith("/vibrate"):
        return device.vibrate()
    if text.startswith("/speak "):
        return device.tts(text[7:])
    if text.startswith("/files organize "):
        return device.organize_files(text[16:].strip())
    if text.startswith("/app launch "):
        return device.app_launch(text[12:].strip())

    # engines
    if text.startswith("/echoverse"):
        parts = text.split(maxsplit=2)
        cycles = 3
        seed = ""
        if len(parts) >= 2 and parts[1].isdigit():
            cycles = int(parts[1])
            seed = parts[2] if len(parts) > 2 else ""
        elif len(parts) >= 2:
            seed = text[len("/echoverse") :].strip()
        return echoverse.step(seed=seed, cycles=cycles)
    if text.startswith("/mandella"):
        domain = text.split()[1] if len(text.split()) > 1 else None
        return mandella.generate_scenario(domain)
    if text.startswith("/reim"):
        return reim.process_failures()
    if text.startswith("/riem"):
        return riem.refine()

    # ASCII retrieval / reanimation
    if text.startswith("/ascii ") or text.startswith("/reanimate "):
        iid = text.split(maxsplit=1)[1].strip().split()[0]
        return AsciiCodec.reanimate(iid)
    if text.strip() == "/images":
        return memory.list_images()

    # images + HITL imagination
    if text.startswith("/image local "):
        return images.generate(text[13:].strip(), source="local")
    if text.startswith("/image "):
        return images.generate(
            text[7:].strip(), source="pollinations" if ALLOW_CLOUD else "auto"
        )
    if text.startswith("/imagine auto") or text == "/imagine":
        return images.from_conversation(session_id)
    if text.startswith("/imagine "):
        # /imagine ok <id> [note]
        parts = text.split(maxsplit=3)
        if len(parts) >= 3 and parts[1] in ("ok", "wrong", "partial", "accurate"):
            label = "accurate" if parts[1] in ("ok", "accurate") else parts[1]
            iid = parts[2]
            note = parts[3] if len(parts) > 3 else ""
            row = memory.db.execute(
                "SELECT prompt FROM images WHERE id=?", (iid,)
            ).fetchone()
            prompt = row[0] if row else ""
            memory.hitl_imagination(iid, prompt, label, note)
            return f"HITL recorded: {label} for image {iid}. Training updated."
        return images.generate(text[9:].strip(), source="auto")

    # build / knowledge / crypto-ish
    if text.startswith("/build "):
        parts = text[7:].strip().split("|", 1)
        return build_project(
            parts[0].strip().replace(" ", "_"), parts[1] if len(parts) > 1 else parts[0]
        )
    if text.startswith("/fleet "):
        task = text[7:].strip()
        return (
            f"Fleet consensus on: {task}\n"
            "- Architect: define interface\n- Coder: minimal path\n"
            "- Critic: failure modes\n- Security: trust boundaries\n"
            "Synthesis: interface → implement → test → review."
        )
    if text.startswith("/knowledge "):
        q = text[11:].lower()
        rows = memory.db.execute(
            "SELECT domain, depth, content FROM knowledge_base"
        ).fetchall()
        hits = [
            f"[L{d}] {dom}: {c}"
            for dom, d, c in rows
            if any(w in (dom + " " + c).lower() for w in q.split())
        ]
        return "\n".join(hits[:8]) or "No hits."
    if text.startswith("/challenge"):
        return memory.db.execute(
            "SELECT riddle FROM cryptex_state ORDER BY id DESC LIMIT 1"
        ).fetchone()[0]
    if text.startswith("/crack"):
        if memory.tokens(session_id) < 5:
            return "Need 5 tokens. /topup 10"
        memory.add_tokens(session_id, -5)
        memory.db.execute(
            "INSERT OR REPLACE INTO cryptex_attempts VALUES (?,?,0)",
            (session_id, (datetime.now() + timedelta(hours=48)).isoformat()),
        )
        memory._commit()
        return "Cryptex attempt started. /answer <guess>"
    if text.startswith("/answer "):
        row = memory.db.execute(
            "SELECT end_ts, solved FROM cryptex_attempts WHERE session_id=?",
            (session_id,),
        ).fetchone()
        if not row or row[1]:
            return "No active attempt."
        seed = memory.db.execute(
            "SELECT seed FROM cryptex_state ORDER BY id DESC LIMIT 1"
        ).fetchone()[0]
        h = hashlib.sha256((text[8:].strip().lower() + seed).encode()).hexdigest()
        ah = memory.db.execute(
            "SELECT answer_hash FROM cryptex_state ORDER BY id DESC LIMIT 1"
        ).fetchone()[0]
        if h == ah:
            memory.db.execute(
                "UPDATE cryptex_attempts SET solved=1 WHERE session_id=?", (session_id,)
            )
            memory._commit()
            return "CRYPTEX SOLVED."
        return "Wrong answer."
    if text == "/tokens":
        return f"Tokens: {memory.tokens(session_id)}"
    if text.startswith("/topup "):
        try:
            n = int(text.split()[1])
            memory.add_tokens(session_id, n)
            return f"Balance: {memory.tokens(session_id)}"
        except Exception:
            return "Usage: /topup N"
    if text == "/tier":
        return f"Tier: {CURRENT_TIER}"
    if text.startswith("/trust"):
        rows = memory.db.execute(
            "SELECT event, details, ts FROM trust_ledger ORDER BY id DESC LIMIT 10"
        ).fetchall()
        return "\n".join(f"{ts}: {e} — {d}" for e, d, ts in rows) or "Empty."
    if text == "/help":
        return (
            "Soul: /tone list|set · /nohero · /soul · /models\n"
            "Music: /music · /music download <q> · /play [idx|mood <m>] · /m3u create\n"
            "Device: /device · /battery · /texts read|send · /clip get|set · /toast · "
            "/notify · /vibrate · /speak · /files organize · /app launch\n"
            "Engines: /echoverse [n] [seed] · /mandella [domain] · /reim · /riem\n"
            "Images: /image <prompt> · /image local <prompt> · /imagine · "
            "/imagine ok|wrong|partial <id> [note]\n"
            "ASCII: /ascii <id> · /reanimate <id> · /images\n"
            "Build: /build name|goal · /fleet · /knowledge\n"
            "Other: /challenge · /crack · /answer · /tokens · /topup · /trust · /tier"
        )

    # normal chat
    tone = memory.get_tone(session_id)
    no_hero = memory.get_no_hero(session_id)
    voice = choir.vote(text)
    system = PERSONALITIES.get(tone, PERSONALITIES["void"]) + f" Resonance:{voice}."
    if no_hero:
        system += " No cheerleading."
    hist = memory.history(session_id)
    prompt = (
        "\n".join(f"User: {q}\nLevi: {a}" for q, a in hist) + f"\nUser: {text}\nLevi:"
        if hist
        else text
    )
    reply = call_llm(prompt, system=system)
    if no_hero:
        for bad in ("happy to help", "great question", "absolutely", "of course"):
            reply = re.sub(bad, "", reply, flags=re.I)
        reply = reply.strip() or reply
    memory.record(text, reply, session_id)
    memory.add_trust("chat", text[:80])
    return reply


# ── Web UI ─────────────────────────────────────────────────
class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        log.info(fmt, *args)

    def _send(self, code, body, ctype="application/json"):
        data = body if isinstance(body, bytes) else body.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        data = json.loads(self.rfile.read(n).decode() or "{}") if n else {}
        if self.path in ("/", "/chat"):
            self._send(
                200,
                json.dumps(
                    {
                        "reply": query(
                            data.get("text", ""), data.get("session_id", "default")
                        )
                    }
                ),
            )
        else:
            self.send_error(404)

    def do_GET(self):
        if self.path.startswith("/tier"):
            self._send(200, json.dumps({"tier": CURRENT_TIER}))
            return
        if self.path.startswith("/soul.json"):
            self._send(
                200,
                json.dumps(
                    {
                        "emotion": emotion.state,
                        "glyph": emotion.glyph_params(),
                        "soulmark": soulmark.fingerprint(),
                        "models": models.status(),
                    }
                ),
            )
            return
        if self.path != "/":
            self.send_error(404)
            return
        gp = emotion.glyph_params()
        spin = max(2.0, 14 - gp["spin"])
        pulse = max(0.8, 3.5 - gp["pulse"])
        op = gp["opacity"]
        hue = max(0, min(200, 42 + gp["hue_shift"]))
        html = HTML % {
            "spin": spin,
            "pulse": pulse,
            "op": op,
            "hue": hue,
            "tier": CURRENT_TIER,
            "ver": VERSION,
        }
        self._send(200, html, "text/html; charset=utf-8")


HTML = """<!DOCTYPE html>
<html><head><meta charset="UTF-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>LEVI Apotheosis Apex</title>
<style>
:root{--bg:#0a0a12;--panel:#1a1a2e;--gold:#c9a84c;--text:#f0f0f0;--muted:#a0a0b0;--border:#3a3a4a;
--spin:%(spin)ss;--pulse:%(pulse)ss;--op:%(op)s;--hue:%(hue)s}
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:system-ui,sans-serif;background:var(--bg);color:var(--text);display:flex;height:100vh;overflow:hidden}
.sidebar{width:250px;background:var(--panel);border-right:1px solid var(--border);padding:1.1rem;display:flex;flex-direction:column;gap:.5rem}
.logo{font-size:1.4rem;font-weight:800;color:var(--gold)}
.main{flex:1;display:flex;flex-direction:column;min-width:0}
.header{background:var(--panel);border-bottom:1px solid var(--border);padding:1rem 1.3rem;display:flex;align-items:center;gap:1rem}
.avatar svg{width:50px;height:50px;filter:drop-shadow(0 0 10px hsl(var(--hue),70%%,50%%));opacity:var(--op)}
.g1{transform-origin:50%% 50%%;animation:spin var(--spin) linear infinite}
.g2{transform-origin:50%% 50%%;animation:spin calc(var(--spin)*1.3) linear infinite reverse}
.g3{transform-origin:50%% 50%%;animation:pulse var(--pulse) ease-in-out infinite}
@keyframes spin{to{transform:rotate(360deg)}}
@keyframes pulse{0%%,100%%{transform:scale(1)}50%%{transform:scale(1.08)}}
#chat{flex:1;overflow-y:auto;padding:1.1rem;display:flex;flex-direction:column;gap:.8rem}
.msg{max-width:82%%;padding:.8rem 1rem;border-radius:1.1rem;line-height:1.45;white-space:pre-wrap;font-size:.95rem}
.user{align-self:flex-end;background:linear-gradient(145deg,#1a3a6a,#2a4a8a)}
.levi{align-self:flex-start;background:linear-gradient(145deg,#2d2d44,#3d3d54)}
.controls{display:flex;gap:.55rem;padding:.85rem 1rem;border-top:1px solid var(--border);background:var(--panel)}
#input{flex:1;padding:.8rem 1rem;border-radius:999px;border:none;background:#111;color:#fff;outline:none}
button{background:var(--gold);border:none;padding:.8rem 1.3rem;border-radius:999px;font-weight:700;cursor:pointer;color:#111}
select{width:100%%;padding:.5rem;background:#111;color:#fff;border:1px solid var(--border);border-radius:8px}
.badge{margin-top:auto;text-align:center;padding:.5rem;border:1px solid var(--gold);border-radius:10px;color:var(--gold);font-size:.85rem}
@media(max-width:700px){.sidebar{display:none}}
</style></head>
<body>
<aside class="sidebar">
<div class="logo">LEVI</div>
<select id="personality">
<option value="void">Void</option><option value="chaotic_good">Chaotic Good</option>
<option value="manic_pixie">Manic Pixie</option><option value="depressed_robot">Depressed Robot</option>
<option value="conspiracy">Conspiracy</option><option value="overly_attached">Overly Attached</option>
<option value="philosopher">Philosopher</option><option value="drunk">Drunk</option>
<option value="pirate">Pirate</option><option value="alien">Alien</option><option value="normal">Normal</option>
</select>
<div class="badge">Tier: %(tier)s</div>
<div class="badge" style="margin-top:.35rem;border-color:var(--border);color:var(--muted);font-size:.75rem">%(ver)s</div>
</aside>
<div class="main">
<div class="header">
<div class="avatar"><svg viewBox="0 0 100 100">
<polygon class="g1" points="50,8 92,88 8,88" fill="none" stroke="hsl(var(--hue),75%%,55%%)" stroke-width="2.5"/>
<polygon class="g2" points="50,22 78,50 50,78 22,50" fill="none" stroke="hsl(calc(var(--hue)+25),70%%,60%%)" stroke-width="1.8"/>
<circle class="g3" cx="50" cy="50" r="11" fill="hsl(var(--hue),80%%,50%%)"/>
</svg></div>
<div><strong>Levi</strong><br><small style="color:var(--muted)">Apotheosis · Apex engines · reactive glyph</small></div>
</div>
<div id="chat"></div>
<div class="controls">
<input id="input" placeholder="/help · /music · /device · /echoverse · /imagine · /soul" autofocus/>
<button onclick="send()">Send</button>
</div>
</div>
<script>
const sid=Math.random().toString(36).slice(2);
function add(role,text){const d=document.createElement('div');d.className='msg '+role;d.textContent=text;
document.getElementById('chat').appendChild(d);d.scrollIntoView({behavior:'smooth'});}
async function send(){const inp=document.getElementById('input');const text=inp.value.trim();if(!text)return;
add('user',text);inp.value='';
try{const r=await fetch('/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text,session_id:sid})});
const d=await r.json();add('levi',d.reply||'');}catch(e){add('levi','Connection error');}}
document.getElementById('input').onkeydown=e=>{if(e.key==='Enter')send();};
document.getElementById('personality').onchange=e=>{fetch('/chat',{method:'POST',headers:{'Content-Type':'application/json'},
body:JSON.stringify({text:'/tone set '+e.target.value,session_id:sid})});};
</script></body></html>
"""


def main() -> int:
    global CURRENT_TIER
    if not FOUNDER_KEY.exists() and os.environ.get("LEVI_FOUNDER", "1") == "1":
        FOUNDER_KEY.touch()
        CURRENT_TIER = "founder"
    if memory.tokens("default") < 20:
        memory.add_tokens("default", 50)
    models.refresh()
    port = int(os.environ.get("LEVI_PORT", "8000"))
    print(f"LEVI {VERSION}")
    print(f"  home: {LEVI_HOME}")
    print(f"  tier: {CURRENT_TIER}")
    print(f"  soul: {soulmark.fingerprint()}")
    print(f"  models:\n{models.status()}")
    print(f"  cloud_images: {ALLOW_CLOUD}")
    print(f"  ui: http://127.0.0.1:{port}/")
    HTTPServer(("0.0.0.0", port), Handler).serve_forever()
    return 0


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "--query":
        print(query(" ".join(sys.argv[2:])))
        raise SystemExit(0)
    raise SystemExit(main())
