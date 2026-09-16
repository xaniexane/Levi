#!/usr/bin/env bash
# wifi_network_audit.sh - report nearby WiFi networks. Report only.
# Never attempts to connect to anything.
set -euo pipefail

echo "=== WiFi network audit (report only, no connections made) ==="

if command -v nmcli >/dev/null 2>&1; then
    echo "--- via nmcli ---"
    # -t: terse, easy to parse. Rescan not requested (may need privileges);
    # shows the most recent scan results.
    if nmcli -t -f SSID,SIGNAL,CHAN,SECURITY dev wifi list 2>/dev/null | \
        awk -F: 'BEGIN{printf "%-32s %6s %7s %s\n","SSID","SIGNAL","CHAN","SECURITY"}
                 {printf "%-32s %6s %7s %s\n",$1,$2,$3,$4}'; then
        exit 0
    fi
    echo "nmcli present but could not list networks (permissions?)"
    exit 1
fi

if command -v iwlist >/dev/null 2>&1; then
    echo "--- via iwlist (fallback) ---"
    iface="$(iw dev 2>/dev/null | awk '/Interface/{print $2; exit}')"
    if [[ -z "${iface:-}" ]]; then
        echo "no wireless interface found via 'iw dev'." >&2
        exit 1
    fi
    echo "interface: $iface"
    # iwlist scan usually needs root; report honestly on failure.
    if ! sudo -n true 2>/dev/null; then
        echo "note: iwlist scanning typically requires root; trying anyway..."
    fi
    sudo iwlist "$iface" scan 2>/dev/null | \
        awk '/Cell/{cell=$0} /ESSID/{essid=$0} /Signal level/{sig=$0} /Channel:/{ch=$0}
             /Encryption key/{enc=$0} {if(enc!=""){print cell; print "  "essid; print "  "sig; print "  "ch; print "  "enc; print ""; enc=""}}' \
        || { echo "iwlist scan failed (needs privileges?)" >&2; exit 1; }
    exit 0
fi

echo "no supported WiFi tool found (looked for nmcli, iwlist)." >&2
echo "install NetworkManager (nmcli) or wireless-tools (iwlist) to run this audit." >&2
exit 2
