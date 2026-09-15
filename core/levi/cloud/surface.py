"""
Unified cloud surface — Phase map + crypto + ZK + sync dry-run for CLI / ops.
"""

from __future__ import annotations

from typing import Any, Dict

from levi.cloud.stages import StageMap
from levi.cloud.crypto_protocol import CryptoProtocol
from levi.cloud.sync_dryrun import SyncDryRun
from levi.cloud.zk import ZeroKnowledgeDesign


class CloudSurface:
    """Single entry used by `levi cloud` and ops integration."""

    def __init__(self) -> None:
        self.phases = StageMap()
        self.crypto = CryptoProtocol()
        self.sync = SyncDryRun()
        self.zk = ZeroKnowledgeDesign()

    def report_phases(self) -> str:
        return self.phases.status_block()

    def report_crypto(self) -> str:
        return self.crypto.full_report()

    def report_argon2(self) -> str:
        return self.crypto.argon.status_block()

    def report_ratchet(self) -> str:
        return self.crypto.ratchet.status_block()

    def report_zk(self) -> str:
        return self.zk.report()

    def report_sync(self) -> str:
        return self.sync.report()

    def report_all(self) -> str:
        parts = [
            self.phases.status_block(),
            "",
            self.crypto.full_report(),
            "",
            self.zk.report(),
            "",
            self.sync.report(),
            "",
            "══ Caps ══",
            "  Phase A: run it (local complete path).",
            "  Phase B: build transport against this protocol.",
            "  Phase C: product wings — still not “cloud that owns your keys.”",
            "  Cloud is optional. Core stays useful offline.",
        ]
        return "\n".join(parts)

    def demo(self) -> Dict[str, Any]:
        return self.crypto.demo_roundtrip()
