#!/usr/bin/env bash
# security_audit.sh - defensive local security checklist. REPORT ONLY.
# This script never changes anything: no firewall edits, no kills,
# no permission changes, no deletions.
set -euo pipefail

section() { echo; echo "=== $1 ==="; }

section "Listening TCP/UDP ports"
if command -v ss >/dev/null 2>&1; then
    ss -tuln 2>/dev/null || echo "(ss failed)"
elif command -v netstat >/dev/null 2>&1; then
    netstat -tuln 2>/dev/null || echo "(netstat failed)"
else
    echo "(neither ss nor netstat available)"
fi

section "Recent failed SSH logins (best effort)"
found=0
if command -v journalctl >/dev/null 2>&1; then
    if journalctl --no-pager -q -n 200 2>/dev/null | grep -i "failed password" | tail -n 20; then
        found=1
    fi
fi
if [[ "$found" -eq 0 ]]; then
    if grep -h "Failed password" /var/log/auth.log* 2>/dev/null | tail -n 20; then
        found=1
    fi
fi
if [[ "$found" -eq 0 ]]; then
    echo "(no auth logs readable -- needs privileges, or no failures recorded)"
fi

section "World-writable files under \$HOME (max depth 4)"
if find "$HOME" -xdev -maxdepth 4 -type f -perm -0002 2>/dev/null | head -n 50 | grep -q .; then
    find "$HOME" -xdev -maxdepth 4 -type f -perm -0002 2>/dev/null | head -n 50
else
    echo "(none found)"
fi

section "Last 10 logins"
if command -v last >/dev/null 2>&1; then
    last -n 10 2>/dev/null || echo "(last failed)"
else
    echo "(last not available)"
fi

echo
echo "audit complete. No changes were made."
