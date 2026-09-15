# Auditing UEFI Firmware with CHIPSEC

## Purpose

Use Intel's CHIPSEC framework to audit platform firmware security configuration on live
systems: BIOS write protection, SMM protections, Secure Boot state, SPI flash descriptor
permissions, and UEFI variable protections — the controls that stop firmware implants and
persistent bootkits.

## When to use

- Hardware/firmware security assessments of endpoints or servers before fleet deployment.
- Incident response where firmware persistence (bootkit) is suspected.
- Validating that OEM firmware settings match the organization's hardening baseline.
- Regression checks after BIOS/UEFI updates — updates reset protections more often than
  vendors admit.

## Prerequisites

- Written authorization and a defined scope: specific machines/systems in bounds (CHIPSEC
  reads low-level hardware state and can crash unstable systems — never run it on
  production without approval and a maintenance window).
- A test machine of the same model/firmware for initial runs; CHIPSEC behavior is
  platform-specific.
- CHIPSEC installed from source (Python 3, plus the kernel driver for your OS — Linux
  needs the `chipsec` kernel module or `/dev/mem` access patterns per the docs; UEFI
  shell builds avoid OS driver issues).
- Root/Administrator privileges — there is no unprivileged CHIPSEC.

## Procedure

1. **Prepare the test system.**
   - Boot the reference machine, install CHIPSEC per the platform instructions, and
     confirm the driver loads (`python chipsec_main.py --help` enumerates without error).
   - Record platform, chipset, BIOS version, and CHIPSEC version — results are meaningless
     without them.

2. **Enumerate available modules.**
   - Run `python chipsec_main.py -l "*"` (list modules) to see what's supported on this
     platform; unsupported modules error out rather than silently passing.

3. **Check BIOS write protection.**
   - Run `python chipsec_main.py -m common.bios_wp` — verifies BIOS Control register
     protections (BIOSWE, BLE, SMM_BWP) that prevent unsigned SPI flash writes.
   - Any FAILED result here means firmware can be rewritten from the OS — the highest
     severity firmware finding.

4. **Check SMM protections.**
   - Run `python chipsec_main.py -m common.bios_ts` (Transaction Security) and
     `common.smm` — validates SMRAM locking and SMI handler protections.
   - Weak SMM configuration enables SMM implants, the stealthiest firmware persistence.

5. **Verify Secure Boot state.**
   - Run `python chipsec_main.py -m common.secureboot` — checks Secure Boot is enabled
     and the platform key / key exchange keys match expectations.
   - Compare PK/KEK/db against the organization's expected keys, not just "enabled" —
     an attacker-controlled PK with Secure Boot "on" is worse than useless.

6. **Audit the SPI flash descriptor.**
   - Run the descriptor modules (`common.spi_desc`, `common.spi_lock`) to verify flash
     descriptor permissions and SPI controller locks.
   - Confirm the descriptor itself is locked — an unlocked descriptor lets software
     repartition flash access.

7. **Dump and analyze the firmware image (authorized).**
   - Use `python chipsec_util.py spi dump rom.bin` to extract the SPI flash image.
   - Analyze offline: `python chipsec_util.py uefi decode rom.bin`, then scan for blocked
     opcodes/behaviors with `tools.uefi.scan_blocked` and review the UEFI variable store.

8. **Check UEFI variable protections.**
   - Run `common.uefi.access_uefispec` to verify authenticated variables (BootOrder,
     Secure Boot keys) can't be modified without proper authentication.
   - Flag writable-when-they-shouldn't-be variables — these are bootkit footholds.

9. **Record, remediate, re-test.**
   - For each FAILED/WARNING module record the register values and the expected secure
     state.
   - Remediation is usually a BIOS setting change or firmware update — apply on the test
     machine first, re-run the module, and only then roll out with the platform team.

## Key tools & commands

- `python chipsec_main.py -m <module>` — run a security assessment module; `-m
  common.bios_wp`, `common.bios_ts`, `common.smm`, `common.secureboot` are the core set.
- `python chipsec_main.py -l "*"` — list available modules for the platform.
- `python chipsec_util.py spi dump rom.bin` / `spi read` — extract flash for offline
  analysis.
- `python chipsec_util.py uefi decode rom.bin` — parse the dumped firmware image.
- `tools.uefi.scan_blocked` — scan the image for blocked/suspicious behaviors.

## Expected outputs

- Per-module results (PASSED/FAILED/WARNING/INFORMATION) with register-level evidence.
- Firmware image dump (handled as sensitive — it contains the platform's firmware) and
  decode analysis notes.
- Findings mapped to remediation (BIOS setting, firmware update, key replacement).
- Re-test results confirming closure.

## Pitfalls

- Running CHIPSEC on production without a maintenance window — driver loads and low-level
  reads can hang fragile systems.
- Treating WARNING as passing — on firmware, warnings deserve investigation, not dismissal.
- Platform-specific modules: a module that errors as unsupported is not a finding, but
  note the coverage gap.
- Secure Boot "enabled" with unexpected keys — always compare against the known-good key
  set.

## References

- CHIPSEC documentation (GitHub: chipsec/chipsec) — module reference and platform setup.
- Intel whitepapers on BIOS/SMM security (BIOSWE/BLE/SMM_BWP semantics).
- MITRE ATT&CK: T1542.001 (System Firmware), T1542.003 (Bootkit).
- NIST SP 800-147 (BIOS Protection Guidelines), SP 800-155 (BIOS Integrity Measurement).

---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
