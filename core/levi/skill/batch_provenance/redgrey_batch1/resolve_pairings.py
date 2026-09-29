"""Resolve red->blue pairings: match each red topic's blue_kw against cyber skill IDs.

Deterministic: score = number of distinct blue_kw keywords appearing as substrings
in the cyber ID; pick max score, tie-break alphabetically. Prints the full mapping
for human review. Exits non-zero if any topic has zero candidates.
"""
import importlib, sys

CYBER_IDS = [l.strip() for l in open('/tmp/redgrey_cyber_ids.txt') if l.strip()]

def norm_kw(kw):
    return kw.lower().replace('-', '_').replace(' ', '_')

def candidates_for(topic):
    kws = [norm_kw(k) for k in topic['blue_kw']]
    scored = []
    for cid in CYBER_IDS:
        hits = [k for k in kws if k in cid]
        if hits:
            scored.append((len(hits), cid, hits))
    scored.sort(key=lambda s: (-s[0], s[1]))
    return scored

# Manual overrides: slug -> cyber skill_id (verified by human review).
OVERRIDES = {
"adcs-escalation": "cyber_exploiting_active_directory_certificate_services_esc1",
"ad-enumeration": "cyber_performing_active_directory_bloodhound_analysis",
"amsi-bypass-test": "cyber_deobfuscating_powershell_obfuscated_malware",
"audio-video-capture-test": "cyber_implementing_endpoint_dlp_controls",
"etl-tampering-test": "cyber_configuring_windows_event_logging_for_detection",
"credentialed-file-collection": "cyber_implementing_endpoint_dlp_controls",
"defender-exclusion-abuse": "cyber_configuring_windows_defender_advanced_settings",
"credential-phishing-page": "cyber_analyzing_email_headers_for_phishing_investigation",
"credential-stuffing-test": "cyber_implementing_passwordless_authentication_with_fido2",
"clipboard-credential-capture": "cyber_detecting_insider_data_exfiltration_via_dlp",
"database-collection-test": "cyber_performing_sqlite_database_forensics",
"email-collection-test": "cyber_analyzing_outlook_pst_for_email_forensics",
"exploiting-public-facing-app": "cyber_implementing_web_application_logging_with_modsecurity",
"golden-ticket-persistence": "cyber_detecting_golden_ticket_attacks_in_kerberos_logs",
"hash-cracking-lab": "cyber_implementing_passwordless_authentication_with_fido2",
"lsass-dump-test": "cyber_detecting_credential_dumping_techniques",
"mimikatz-detection-test": "cyber_detecting_mimikatz_execution_patterns",
"sam-ntds-extraction": "cyber_detecting_t1003_credential_dumping_with_edr",
"impact-cleanup-verification": "cyber_conducting_post_incident_lessons_learned",
"indicator-removal-audit": "cyber_building_incident_timeline_with_timesketch",
"network-share-discovery": "cyber_configuring_windows_event_logging_for_detection",
"obfuscation-resilience": "cyber_deobfuscating_powershell_obfuscated_malware",
"office-macro-execution": "cyber_analyzing_macro_malware_in_office_documents",
"password-policy-discovery": "cyber_auditing_azure_active_directory_configuration",
"recovery-time-drill": "cyber_testing_ransomware_recovery_procedures",
"service-fingerprinting": "cyber_detecting_network_reconnaissance_and_port_scanning",
"software-inventory-recon": "cyber_performing_asset_criticality_scoring_for_vulns",
"subdomain-discovery": "cyber_performing_subdomain_enumeration_with_subfinder",
"unquoted-service-path": "cyber_hardening_windows_endpoint_with_cis_benchmark",
"user-hunting-test": "cyber_implementing_privileged_session_monitoring",
"wifi-password-recovery": "cyber_performing_wireless_security_assessment_with_kismet",
"wiper-impact-test": "cyber_testing_ransomware_recovery_procedures",
"wireless-recon": "cyber_performing_wireless_security_assessment_with_kismet",
"domain-fronting-test": "cyber_hunting_for_domain_fronting_c2_traffic",
"https-c2-test": "cyber_hunting_for_command_and_control_beaconing",
"c2-jitter-mimicry": "cyber_analyzing_command_and_control_communication",
"c2-infrastructure-takedown": "cyber_building_incident_response_playbook",
"icmp-tunnel-test": "cyber_configuring_suricata_for_network_monitoring",
"steganography-c2-test": "cyber_performing_steganography_detection",
"steganographic-exfil-test": "cyber_performing_steganography_detection",
"external-remote-service-brute-force": "cyber_detecting_rdp_brute_force_attacks",
}

def main():
    topics = []
    for i in range(1, 8):
        topics.extend(importlib.import_module(f'topics_red{i}').__dict__[f'RED_{i}'])
    pairings = {}
    failures = []
    for t in topics:
        slug = t['slug']
        if slug in OVERRIDES:
            cid = OVERRIDES[slug]
            assert cid in CYBER_IDS, f'override {cid} not a real cyber id'
            pairings[slug] = (cid, 'OVERRIDE')
            continue
        cands = candidates_for(t)
        if not cands:
            failures.append(slug)
            continue
        score, cid, hits = cands[0]
        pairings[slug] = (cid, f'score={score} hits={hits}')
    for slug in sorted(pairings):
        cid, how = pairings[slug]
        print(f'{slug}\n    -> {cid}   [{how}]')
    if failures:
        print('\nFAILURES (no blue counterpart found):', file=sys.stderr)
        for s in failures:
            print('  ' + s, file=sys.stderr)
        sys.exit(1)
    print(f'\n{len(pairings)} pairings resolved, 0 failures', file=sys.stderr)

if __name__ == '__main__':
    import os
    os.chdir('/tmp/redgrey')
    sys.path.insert(0, '/tmp/redgrey')
    main()
