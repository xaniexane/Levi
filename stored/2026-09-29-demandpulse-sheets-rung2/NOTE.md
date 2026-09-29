# Snapshot — sheets leg rung 2 (2026-09-29)

Pre-edit copy of `core/levi/demand/failover.py` before adding the
second rung to `send_sheets`: direct append to the DemandPulse Google
Sheet via `hatch_gws_cli` when `LEVI_SHEETS_WEBHOOK_URL` is unset.

Why: Chauncey ruled "Google Sheets with webhooks" and said "you can do
it" — the DemandPulse sheet exists (created 2026-09-29 via the Sheets
API); this makes the sheets leg actually deliver without waiting on
his Apps Script URL. Chain order unchanged (sheets stays last).
