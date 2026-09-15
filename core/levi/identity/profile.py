"""
User profile + first-run state — retention DNA.
Local-only under ~/.levi/profile.json
"""

from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional
from pathlib import Path
from datetime import datetime, timezone
import json

DEFAULT_DIR = Path.home() / ".levi"
PROFILE_PATH = DEFAULT_DIR / "profile.json"


@dataclass
class UserProfile:
    name: str = ""
    goal_this_week: str = ""
    preferred_loop: str = ""  # writing | building | companion | ""
    verbose: bool = False
    confirm_constructive: bool = True  # confirm before factory/story auto-run
    onboarded: bool = False
    last_active: str = ""
    last_continued: str = ""  # last project/story id hint
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    notes: List[str] = field(default_factory=list)
    pending_skill: str = ""
    pending_text: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "UserProfile":
        known = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore
        return cls(**{k: v for k, v in d.items() if k in known})


class ProfileStore:
    def __init__(self, path: Optional[Path] = None):
        self.path = Path(path) if path else PROFILE_PATH
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> UserProfile:
        if not self.path.exists():
            return UserProfile()
        try:
            return UserProfile.from_dict(
                json.loads(self.path.read_text(encoding="utf-8"))
            )
        except Exception:
            return UserProfile()

    def save(self, profile: UserProfile) -> None:
        profile.last_active = datetime.now(timezone.utc).isoformat()
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(profile.to_dict(), indent=2), encoding="utf-8")
        tmp.replace(self.path)

    def is_onboarded(self) -> bool:
        return self.load().onboarded
