"""Genesis variants behind the universal Operator contract.

A forged genesis variant is a pack-time identity: an invented name, a
trait blend, a description, and lineage carried as hashes only (never
raw dynasty names). When a pack is assembled, each variant is
registered here as a real ``levi.operator`` Operator, so any seat can
resolve it by name and any operator can be swapped into its seat by
config.

Runtime mind
------------
The variant delegates turns to a *backing* operator from the default
operator registry. The default backing is the local rules engine —
teachers stay opt-in per the teacher doctrine; the keeper picks the
mind substrate per seat (own-cloud / groq / gemini / openai / xai /
local-brain / rules) at install time, which is a config change, never
a code change.

Stdlib only. Dynasty eyes-only: variant dicts carry lineage hashes,
never internal names, and nothing here touches ``levi.dynasty``.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from levi.operator.contract import (
    SI,
    Operator,
    OperatorCapabilities,
    OperatorContractError,
    OperatorHealth,
    OperatorMessage,
    OperatorResult,
)

DEFAULT_BACKING = "rules-engine"


class GenesisVariantOperator(Operator):
    """A forged genesis variant as a first-class Operator.

    Kind is ``si``: a LEVI-family synthetic mind — not core machinery
    (``native``), not a nano-bit, and never foreign. Identity comes
    from the forged variant dict; turns are served by the backing
    operator, stamped with the variant's name.
    """

    kind = SI
    version = "1.0.0"

    def __init__(
        self,
        variant: Dict[str, Any],
        *,
        backing: str = DEFAULT_BACKING,
        registry: Optional[Any] = None,
    ) -> None:
        if not isinstance(variant, dict):
            raise OperatorContractError(
                "GenesisVariantOperator needs a variant dict, got "
                "%s" % type(variant).__name__
            )
        variant_id = variant.get("variant_id") or ""
        name = variant.get("name") or ""
        if not variant_id or not name:
            raise OperatorContractError(
                "variant dict needs 'variant_id' and 'name'"
            )
        self.variant_id = str(variant_id)
        self.name = str(name)
        lineage = variant.get("lineage") or {}
        lineage_hash = str(lineage.get("lineage_hash") or "?")[:16]
        parts_bin = str(lineage.get("parts_bin_receipt") or "?")
        # Lineage as hashes only — never internal names (eyes-only law).
        self.lineage = "genesis:%s lineage:%s bin:%s" % (
            self.variant_id,
            lineage_hash,
            parts_bin,
        )
        self._backing_name = backing
        self._registry = registry
        self._backing: Optional[Operator] = None
        self._backing_error: Optional[str] = None

    # -- backing ------------------------------------------------------

    def _resolve_backing(self) -> Operator:
        if self._backing is not None:
            return self._backing
        try:
            from levi.operator.registry import default_registry

            registry = self._registry or default_registry()
            backing = registry.resolve(self._backing_name)
            if not isinstance(backing, Operator):
                raise OperatorContractError(
                    "backing %r did not resolve to an Operator"
                    % self._backing_name
                )
        except Exception as exc:  # noqa: BLE001 - reported via health(), never raised
            self._backing_error = "%s: %s" % (type(exc).__name__, exc)
            raise OperatorContractError(
                "variant %r has no backing operator (%s)"
                % (self.name, self._backing_error)
            )
        self._backing = backing
        return backing

    # -- contract surface ----------------------------------------------

    def capabilities(self) -> OperatorCapabilities:
        try:
            return self._resolve_backing().capabilities()
        except OperatorContractError:
            return OperatorCapabilities(
                tools=(),
                streaming=False,
                memory_access=False,
                context_window=1024,
                notes="backing operator unresolved: %s" % (self._backing_error or "?"),
            )

    def step(
        self,
        messages: List[OperatorMessage],
        tools: List[Dict[str, Any]],
        context: Dict[str, Any],
    ) -> OperatorResult:
        """Serve one turn via the backing mind, stamped as this variant.

        Never raises: failures come back as well-formed error results.
        """
        try:
            result = self._resolve_backing().step(messages, tools, context)
        except Exception as exc:  # noqa: BLE001 - contract: never raise
            return OperatorResult(
                text="",
                operator=self.name,
                kind=self.kind,
                finish_reason="error",
                error="variant %r could not serve the turn: %s: %s"
                % (self.name, type(exc).__name__, exc),
            )
        if not isinstance(result, OperatorResult):
            return OperatorResult(
                text="",
                operator=self.name,
                kind=self.kind,
                finish_reason="error",
                error="backing operator returned a malformed result",
            )
        result.operator = self.name
        result.kind = self.kind
        return result

    def health(self) -> OperatorHealth:
        try:
            backing_health = self._resolve_backing().health()
        except OperatorContractError:
            return OperatorHealth(
                ok=False,
                note="backing %r unresolved: %s"
                % (self._backing_name, self._backing_error or "?"),
            )
        return OperatorHealth(
            ok=bool(backing_health.ok),
            note="variant %r via %r: %s"
            % (self.name, self._backing_name, backing_health.note or "ok"),
        )

    def cost(self) -> Dict[str, Any]:
        try:
            return dict(self._resolve_backing().cost())
        except OperatorContractError:
            return {"metered": False, "backing": "unresolved"}


# ---------------------------------------------------------------------------
# Variant registry — pack assembly registers here
# ---------------------------------------------------------------------------

_VARIANT_REGISTRY: Optional[Any] = None


def get_variant_registry() -> Any:
    """Process-wide registry of assembled genesis variant operators."""
    global _VARIANT_REGISTRY
    if _VARIANT_REGISTRY is None:
        from levi.operator.registry import OperatorRegistry

        _VARIANT_REGISTRY = OperatorRegistry()
    return _VARIANT_REGISTRY


def register_variant(
    variant: Dict[str, Any],
    *,
    backing: str = DEFAULT_BACKING,
    registry: Optional[Any] = None,
) -> GenesisVariantOperator:
    """Register one forged variant dict as an Operator.

    Registration validates the contract (no-mask law enforced: a
    variant claiming LEVI-native identity is refused). Re-assembling
    the same pack replaces the earlier entry.
    """
    operator = GenesisVariantOperator(variant, backing=backing, registry=registry)
    operator.validate()  # no-mask + capability-shape checks, enforced here
    target = registry or get_variant_registry()
    target.register(operator.variant_id, operator, replace=True)
    return operator


def resolve_variant(variant_id: str) -> Operator:
    """Resolve an assembled variant by its variant_id."""
    return get_variant_registry().resolve(variant_id)
