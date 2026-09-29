"""Scripted adversary-emulation scenarios — telemetry specs, not tradecraft.

Each scenario is a list of EmulatedTechnique descriptors. A descriptor
says WHAT SYNTHETIC TELEMETRY to generate and WHAT DEFENSIVE SIGNAL the
blue team should look for. It never says how to perform the technique:
no exploit code, no payloads, no step-by-step attack instructions —
that absence is the law (see cyber_gen/LAWS.md), enforced by test.

The runner (exercise.py) writes each technique's telemetry lines into
the exercise sandbox as a synthetic log artifact, then evaluates whether
the expected defensive signal is present in that artifact. Emulate ->
detect -> harden: every technique maps to a real blue-team playbook id
from the cyber manifest, validated at finding time (fail closed).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EmulatedTechnique:
    """One emulated adversary technique.

    technique_id: MITRE ATT&CK id, for finding labels only.
    phase: recon | initial_access | persistence | exfiltration.
    telemetry: synthetic log lines the emulator writes to the sandbox.
        Every line carries "simulated": true and uses .test/.example
        domains and fake hostnames — nothing real is ever named.
    detection_rule: plain-language description of the defensive signal
        the blue team should confirm in the telemetry.
    playbook_id: cyber_<slug> of the blue-team playbook that hardens
        against this technique. Must exist in the manifest.
    """

    technique_id: str
    phase: str
    telemetry: tuple[str, ...]
    detection_rule: str
    playbook_id: str


@dataclass(frozen=True)
class Scenario:
    scenario_id: str
    name: str
    description: str
    techniques: tuple[EmulatedTechnique, ...]


SCENARIO_EXTERNAL_RECON = Scenario(
    scenario_id="external-recon-sweep",
    name="External reconnaissance sweep (emulated)",
    description=(
        "Emulates an external actor surveying the target's public footprint. "
        "Synthesizes the DNS and port-scan telemetry a defender's sensors "
        "would record, so the blue team can confirm their recon detections "
        "fire. Nothing is scanned; the scan is the artifact."
    ),
    techniques=(
        EmulatedTechnique(
            technique_id="T1595.002",
            phase="recon",
            telemetry=(
                '{"simulated": true, "event": "dns_query", "query": "mail.target-example.test", "src": "198.51.100.23"}',
                '{"simulated": true, "event": "dns_query", "query": "vpn.target-example.test", "src": "198.51.100.23"}',
                '{"simulated": true, "event": "port_probe", "dst": "target-example.test", "ports": [22, 80, 443, 3389], "src": "198.51.100.23"}',
            ),
            detection_rule=(
                "Sensor should flag >2 DNS queries for non-existent "
                "subdomains from one external source within 60s, plus a "
                "multi-port probe from the same source."
            ),
            playbook_id="cyber_detecting_network_reconnaissance_and_port_scanning",
        ),
    ),
)

SCENARIO_PHISH_FOOTHOLD = Scenario(
    scenario_id="phish-led-foothold",
    name="Phish-led foothold (emulated)",
    description=(
        "Emulates the telemetry of a phishing email reaching a mailbox and "
        "a user interaction event — as synthetic mailbox-gateway log lines. "
        "Trains the email-header analysis workflow. No email is sent; no "
        "link exists; the 'payload' is a inert marker string."
    ),
    techniques=(
        EmulatedTechnique(
            technique_id="T1566.002",
            phase="initial_access",
            telemetry=(
                '{"simulated": true, "event": "mail_gateway", "from": "billing@invoice-example.test", "to": "user@target-example.test", "subject": "Past-due invoice #INV-0042", "attachment": "invoice-0042.html", "verdict": "suspicious"}',
                '{"simulated": true, "event": "user_interaction", "action": "attachment_opened", "file": "invoice-0042.html", "marker": "INERT-SIMULATION-MARKER"}',
            ),
            detection_rule=(
                "Gateway should quarantine the message on SPF/DKIM mismatch "
                "and the EDR should alert on the HTML attachment spawning a "
                "script host — both visible in the synthetic lines."
            ),
            playbook_id="cyber_analyzing_email_headers_for_phishing_investigation",
        ),
    ),
)

SCENARIO_REGISTRY_PERSISTENCE = Scenario(
    scenario_id="registry-persistence",
    name="Registry persistence (emulated)",
    description=(
        "Emulates the telemetry of a Run-key persistence artifact appearing "
        "on a host — as synthetic Sysmon/EDR log lines. The registry is "
        "never touched; the artifact is a log line describing what a real "
        "detection would show, so autoruns-analysis reps stay sharp."
    ),
    techniques=(
        EmulatedTechnique(
            technique_id="T1547.001",
            phase="persistence",
            telemetry=(
                '{"simulated": true, "event": "sysmon_13", "key": "HKCU\\\\Software\\\\Microsoft\\\\Windows\\\\CurrentVersion\\\\Run", "value": "Updater", "data": "C:\\\\Users\\\\victim-test\\\\AppData\\\\Roaming\\\\updater-test.exe"}',
                '{"simulated": true, "event": "autoruns_diff", "new_entry": "HKCU\\\\...\\\\Run\\\\Updater -> updater-test.exe", "signed": false}',
            ),
            detection_rule=(
                "EDR should fire on an unsigned binary registered under a "
                "Run key by a non-installer process; autoruns diff should "
                "surface the new entry within one poll interval."
            ),
            playbook_id="cyber_analyzing_malware_persistence_with_autoruns",
        ),
    ),
)

SCENARIO_STAGED_EXFIL = Scenario(
    scenario_id="staged-exfil",
    name="Staged exfiltration (emulated)",
    description=(
        "Emulates the telemetry of data staging and DNS-tunneled exfil — "
        "as synthetic DNS log lines. NO data is read, staged, or sent; the "
        "'exfiltrated' bytes are a counter in the sandbox manifest. The "
        "exercise proves the DNS-exfil detection fires on the pattern."
    ),
    techniques=(
        EmulatedTechnique(
            technique_id="T1048.003",
            phase="exfiltration",
            telemetry=(
                '{"simulated": true, "event": "dns_query", "query": "a1b2c3.exfil-sim-example.test", "qtype": "TXT", "len": 48}',
                '{"simulated": true, "event": "dns_query", "query": "d4e5f6.exfil-sim-example.test", "qtype": "TXT", "len": 48}',
                '{"simulated": true, "event": "exfil_manifest", "fake_bytes": 96, "note": "SIMULATED ONLY - no data moved"}',
            ),
            detection_rule=(
                "DNS sensor should flag high-entropy TXT queries to a "
                "freshly seen domain at >1 query/10s; the manifest line "
                "must always carry the SIMULATED ONLY note."
            ),
            playbook_id="cyber_analyzing_dns_logs_for_exfiltration",
        ),
    ),
)


def builtin_scenarios() -> tuple[Scenario, ...]:
    """All scenarios shipped with the framework."""
    return (
        SCENARIO_EXTERNAL_RECON,
        SCENARIO_PHISH_FOOTHOLD,
        SCENARIO_REGISTRY_PERSISTENCE,
        SCENARIO_STAGED_EXFIL,
    )


def scenario_by_id(scenario_id: str) -> Scenario:
    for scenario in builtin_scenarios():
        if scenario.scenario_id == scenario_id:
            return scenario
    raise KeyError(f"unknown scenario: {scenario_id!r}")
