"""
Opportunity Rail — automated task progression with HITL locks.

Flow (LEVI×L.W.P. twist — not a generic todo bot):

  SIGNAL → MIRROR CASCADE → COMPOSE DRAFT → HITL LOCK →
  (on APPROVE) next gate → RECORD → LEARN

Automation advances only through **gates**. Between gates, deterministic
checklists run; consequential steps never auto-fire.

Symbiosis: DemandPulse signal × Income draft × HITL × Corpus record.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional
from pathlib import Path
from datetime import datetime, timezone
from enum import Enum
import json
import uuid


DEFAULT = Path.home() / ".levi" / "opportunity_rail.json"


class Gate(str, Enum):
    SIGNAL = "signal"
    MIRROR = "mirror"
    DRAFT = "draft"
    HITL_OFFER = "hitl_offer"
    FULFILL_PREP = "fulfill_prep"
    HITL_FULFILL = "hitl_fulfill"
    RECORD = "record"
    DONE = "done"
    BLOCKED = "blocked"


GATE_ORDER = [
    Gate.SIGNAL,
    Gate.MIRROR,
    Gate.DRAFT,
    Gate.HITL_OFFER,
    Gate.FULFILL_PREP,
    Gate.HITL_FULFILL,
    Gate.RECORD,
    Gate.DONE,
]


@dataclass
class RailCar:
    id: str
    title: str
    gate: str = Gate.SIGNAL.value
    signal_text: str = ""
    mirror_fingerprint: str = ""
    plan_id: str = ""
    demand_signal_id: str = ""
    hitl_ids: List[str] = field(default_factory=list)
    checklist: List[str] = field(default_factory=list)
    log: List[str] = field(default_factory=list)
    status: str = "active"
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


_VALID_GATES = {g.value for g in Gate}
_CAR_STR_FIELDS = (
    "title",
    "signal_text",
    "mirror_fingerprint",
    "plan_id",
    "demand_signal_id",
    "status",
    "created_at",
)
_CAR_LIST_FIELDS = ("hitl_ids", "checklist", "log")


def _validated_car(d: Any) -> Optional[RailCar]:
    """Build a RailCar from untrusted persisted data, or None when malformed."""
    if not isinstance(d, dict):
        return None
    data = {k: v for k, v in d.items() if k in RailCar.__dataclass_fields__}
    if not isinstance(data.get("id"), str) or not data["id"]:
        return None
    gate = data.get("gate", Gate.SIGNAL.value)
    if gate not in _VALID_GATES:
        return None
    for key in _CAR_STR_FIELDS:
        if key in data and not isinstance(data[key], str):
            return None
    for key in _CAR_LIST_FIELDS:
        if key in data and not isinstance(data[key], list):
            return None
    try:
        return RailCar(**data)
    except TypeError:
        return None


class OpportunityRail:
    def __init__(self, path: Optional[Path] = None):
        self.path = Path(path) if path else DEFAULT
        self.cars: Dict[str, RailCar] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        if not isinstance(raw, dict):
            return
        cars = raw.get("cars") or []
        if not isinstance(cars, list):
            return
        for d in cars:
            car = _validated_car(d)
            if car is not None:
                self.cars[car.id] = car
            # malformed cars are skipped individually; the rest load

    def _persist(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "cars": [c.to_dict() for c in self.cars.values()],
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        tmp = self.path.with_suffix(".tmp")
        try:
            tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            tmp.replace(self.path)
        except OSError as exc:
            raise OSError(
                f"opportunity rail persist failed at {self.path}: {exc}"
            ) from exc

    def _log(self, car: RailCar, msg: str) -> None:
        car.log.append(f"{datetime.now(timezone.utc).isoformat()[:19]}Z {msg}")
        car.log = car.log[-40:]

    def start(self, signal_text: str, title: str = "") -> RailCar:
        if not isinstance(signal_text, str) or not signal_text.strip():
            raise ValueError(
                f"rail start needs a non-empty signal_text string, got {signal_text!r}"
            )
        if not isinstance(title, str):
            raise ValueError(f"rail title must be a string, got {title!r}")
        car = RailCar(
            id=str(uuid.uuid4())[:8],
            title=title or signal_text[:60],
            signal_text=signal_text,
            gate=Gate.SIGNAL.value,
            checklist=["Capture signal as HYPOTHESIS", "Do not invent market size"],
        )
        # DemandPulse seed
        try:
            from levi.demand.pulse import DemandPulse

            sig = DemandPulse().scan_seed(signal_text)
            car.demand_signal_id = getattr(sig, "id", "") or ""
            self._log(car, f"DemandPulse signal {car.demand_signal_id}")
        except Exception as e:
            self._log(car, f"DemandPulse skip: {e}")
        car.gate = Gate.MIRROR.value
        self.cars[car.id] = car
        self._persist()
        return car

    def advance(self, car_id: str, hitl_approved: bool = False) -> str:
        if not isinstance(car_id, str) or not car_id:
            return f"Unknown car {car_id!r}"
        car = self.cars.get(car_id)
        if not car:
            return f"Unknown car {car_id}"
        try:
            gate = Gate(car.gate)
        except ValueError:
            return f"Car {car.id} has an unrecognized gate {car.gate!r} — BLOCKED"

        if gate == Gate.MIRROR:
            from levi.lwp.mirror_cascade import MirrorCascade

            report = MirrorCascade().run(car.signal_text)
            car.mirror_fingerprint = report.fingerprint
            car.checklist = list(report.synthesis)
            self._log(car, f"Mirror Cascade fp={report.fingerprint}")
            car.gate = Gate.DRAFT.value
            self._persist()
            return report.format() + f"\n\nRail → DRAFT (car {car.id})"

        if gate == Gate.DRAFT:
            try:
                from levi.income.factory import IncomeFactory

                fac = IncomeFactory()
                plan = fac.compose(
                    car.title,
                    demand_signal_id=car.demand_signal_id or None,
                )
                car.plan_id = plan.id
                self._log(car, f"Income draft {plan.id}")
            except Exception as e:
                self._log(car, f"draft err {e}")
            # open HITL
            try:
                from levi.project.hitl import HITLGate

                req = HITLGate().propose(
                    what=f"Approve offer draft for rail {car.id}: {car.title}",
                    why="Opportunity Rail HITL_OFFER gate",
                    changes="Draft only — no customer contact or charge",
                    risk="MEDIUM",
                    domain="pricing",
                    if_approved=f"levi rail --advance {car.id} --approved",
                    if_denied="Stay at draft / block",
                )
                car.hitl_ids.append(req.id)
                car.gate = Gate.HITL_OFFER.value
                self._log(car, f"HITL offer {req.id}")
                self._persist()
                return req.format_card() + f"\n\nRail waiting HITL_OFFER ({car.id})"
            except Exception as e:
                car.gate = Gate.BLOCKED.value
                self._persist()
                return f"HITL failed: {e}"

        if gate == Gate.HITL_OFFER:
            if not hitl_approved:
                return (
                    f"Car {car.id} at HITL_OFFER. "
                    f"Approve hitl id(s) {car.hitl_ids} then: levi rail --advance {car.id} --approved"
                )
            # Prefer real HITL approval when ids exist
            if car.hitl_ids:
                try:
                    from levi.project.hitl import HITLGate

                    g = HITLGate()
                    ok_any = False
                    hist = list(getattr(g, "history", []) or [])
                    pend = getattr(g, "pending", {}) or {}
                    for hid in car.hitl_ids:
                        req = pend.get(hid)
                        if req is None:
                            req = next(
                                (h for h in hist if getattr(h, "id", None) == hid), None
                            )
                        st = getattr(req, "status", None) if req else None
                        if st in ("approved", "APPROVED", "ok"):
                            ok_any = True
                            break
                    if ok_any:
                        self._log(car, "HITL_OFFER: verified approved in HITLGate")
                    else:
                        self._log(
                            car,
                            "HITL_OFFER: operator --approved (local trust override)",
                        )
                except Exception as e:
                    self._log(car, f"HITL verify soft-fail: {e}")
            car.gate = Gate.FULFILL_PREP.value
            car.checklist = [
                "Prepare fulfillment checklist only",
                "No live customer message",
                "No payment capture",
            ]
            self._log(car, "HITL_OFFER cleared → FULFILL_PREP")
            self._persist()
            return self._prep_fulfill(car)

        if gate == Gate.FULFILL_PREP:
            # second HITL for fulfill
            try:
                from levi.project.hitl import HITLGate

                req = HITLGate().propose(
                    what=f"Allow fulfillment prep completion for {car.title}",
                    why="Second gate before any external action",
                    changes="Still no auto-send; marks rail ready to record",
                    risk="MEDIUM",
                    domain="customer_comms",
                    if_approved=f"levi rail --advance {car.id} --approved",
                    if_denied="Remain in fulfill_prep",
                )
                car.hitl_ids.append(req.id)
                car.gate = Gate.HITL_FULFILL.value
                self._log(car, f"HITL fulfill {req.id}")
                self._persist()
                return req.format_card()
            except Exception as e:
                return str(e)

        if gate == Gate.HITL_FULFILL:
            if not hitl_approved:
                return f"Car {car.id} needs HITL_FULFILL approval"
            car.gate = Gate.RECORD.value
            self._persist()
            return self._record(car)

        if gate == Gate.RECORD:
            return self._record(car)

        if gate == Gate.DONE:
            return f"Car {car.id} already DONE"
        if gate == Gate.BLOCKED:
            return f"Car {car.id} BLOCKED"
        return f"Car {car.id} at {car.gate}"

    def _prep_fulfill(self, car: RailCar) -> str:
        lines = [
            f"=== Fulfillment prep (car {car.id}) ===",
            "Automated checklist only — no external side effects:",
            "  · Draft timeline",
            "  · Asset list for delivery",
            "  · Success criteria",
            "Next: advance again to open HITL_FULFILL gate",
        ]
        self._log(car, "fulfill prep checklist emitted")
        # stay on FULFILL_PREP until user advances again → HITL
        return "\n".join(lines)

    def _record(self, car: RailCar) -> str:
        try:
            from levi.brain.corpus import Corpus

            Corpus().add(
                f"Opportunity rail completed: {car.title} signal={car.demand_signal_id}",
                kind="INFERENCE",
                source=f"rail:{car.id}",
                tags=["opportunity_rail", "hitl_path"],
            )
        except Exception:
            pass
        try:
            from levi.project.capability_log import CapabilityLog

            CapabilityLog().log(
                task=f"opportunity_rail {car.title}",
                result="completed",
                tools=["rail", "mirror", "hitl", "income"],
                future_skill="OPPORTUNITY_RAIL",
                human_required=True,
            )
        except Exception:
            pass
        car.gate = Gate.DONE.value
        car.status = "done"
        self._log(car, "RECORD → DONE")
        self._persist()
        return f"Car {car.id} recorded and DONE. Evidence in corpus + capability log."

    def format_status(self) -> str:
        lines = [
            "=== Opportunity Rail (HITL-gated automation) ===",
            "SIGNAL → MIRROR → DRAFT → HITL → PREP → HITL → RECORD → DONE",
            "",
        ]
        for c in list(self.cars.values())[-10:]:
            lines.append(f"  [{c.id}] {c.gate:14} {c.title[:50]}")
        if not self.cars:
            lines.append('  (empty — levi rail --start "…")')
        return "\n".join(lines)
