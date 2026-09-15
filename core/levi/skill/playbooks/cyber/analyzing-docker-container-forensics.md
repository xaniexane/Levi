---
skill_id: cyber_analyzing_docker_container_forensics
name: Analyzing Docker Container Forensics
description: Forensics for compromised containers: layer diffs, exec history, and runtime artifacts.
risk: low
permissions: []
requires_confirmation: false
tags: [forensics, cloud]
version: 1.0.0
---
# Analyzing Docker Container Forensics

## Purpose

Containers are ephemeral by design, but they leave rich forensic traces on the host:
layer filesystems, container metadata, runtime logs, and kernel-level audit records.
This playbook shows how to collect and analyze those traces when a container is
suspected of compromise, cryptomining, or being a launchpad for lateral movement.
The goal is a defensible timeline of what the container did and what changed.

## When to use

- A running or stopped container behaves suspiciously (unexpected network egress,
  high CPU, unknown processes).
- An image is suspected of containing a backdoor, miner, or malicious layer.
- You need to determine the blast radius of a container escape or breakout attempt.
- Post-incident: reconstruct container activity after the container was removed.

## Prerequisites

- Written authorization to examine the host; do not image or interrogate
  production systems without approval from the system owner.
- Root or docker-group access on the host (needed to read `/var/lib/docker`).
- Chain of custody: record host name, time, and a hash of every artifact you copy
  off the host before analysis. Work on copies, not the live filesystem.
- A forensic workstation with the Docker CLI, `dive`, and a text/JSON tool (`jq`).

## Procedure

1. Identify the containers and their state:
   `docker ps -a --no-trunc` and note container IDs, images, and status.
2. Capture runtime metadata before touching anything:
   `docker inspect <container-id> > container-inspect.json`
   This records mounts, network settings, environment variables, entrypoint,
   and the image digest. Hash the file immediately.
3. Preserve the container's filesystem as it exists now:
   `docker export <container-id> -o container-fs.tar`
   then `sha256sum container-fs.tar` and log the hash.
4. Capture stdout/stderr logs:
   `docker logs --timestamps <container-id> > container-logs.txt 2>&1`
5. List files changed relative to the image:
   `docker diff <container-id>`
   Added (A), changed (C), and deleted (D) files are the primary lead list —
   dropped binaries, new cron entries, and modified configs show up here.
6. Examine image layer history for supply-chain tampering:
   `docker history --no-trunc <image>` and `dive <image>`
   Look for unexpected `ADD`/`COPY` of binaries, curl-piped-to-shell patterns,
   or layers added after the official base image layers.
7. Check mounts and volumes for host exposure:
   from the inspect JSON, review `Mounts` — especially bind mounts of `/`,
   `/var/run/docker.sock`, or the host Docker socket, which enable breakout.
8. Review network activity:
   `docker network inspect <network>` for the container's peers; on the host,
   correlate with `conntrack -L`, firewall logs, or `tcpdump` captures if running.
9. Look for persistence mechanisms inside the container diff:
   `/etc/crontab`, `/etc/cron.d/*`, systemd units, shell rc files,
   and any new setuid binaries (`find <extracted-fs> -perm -4000`).
10. Check the host audit trail for container escapes:
    `ausearch -m AVC -ts recent` (SELinux/AppArmor denials) and review
    `/var/log/audit/audit.log` for suspicious `execve` or mount syscalls
    from containerd-shim processes.
11. If the container is already deleted, fall back to host artifacts:
    image layers under `/var/lib/docker/overlay2/`, container configs under
    `/var/lib/docker/containers/<id>/config.v2.json` and `*-json.log`, which
    often survive after `docker rm`.
12. Build a timeline: merge container logs, `docker diff` findings, host audit
    events, and layer timestamps into one chronological narrative.

## Key tools & commands

- `docker inspect <id>` — full runtime metadata (mounts, env, network, image).
- `docker export <id> -o fs.tar` — snapshot the writable layer as a tarball.
- `docker diff <id>` — files added/changed/deleted vs. the image.
- `docker logs --timestamps <id>` — captured stdout/stderr.
- `docker history --no-trunc <image>` — layer build history.
- `dive <image>` — interactive layer-by-layer filesystem explorer.
- `docker network inspect <net>` — container network membership.
- `ctr -n k8s.io containers list` / `crictl ps -a` — for containerd/CRI hosts
  where the Docker CLI is absent.
- `jq` — parsing inspect JSON, e.g. `.[] | .Mounts`.
- `ausearch -m AVC,EXECVE -ts <range>` — host audit trail around the incident.

## Expected outputs

- Hashed copies of: inspect JSON, exported filesystem tar, container logs.
- A list of anomalous files from `docker diff` with hashes and VirusTotal /
  internal-sandbox dispositions.
- Image layer findings: unexpected binaries, suspicious build commands.
- A timeline correlating container activity with host audit events.
- A containment recommendation (quarantine image, rotate secrets mounted in,
  review sibling containers from the same image).

## Pitfalls

- `docker logs` only shows stdout/stderr — a quiet attacker leaves nothing there.
  Do not treat empty logs as evidence of a clean container.
- `docker rm` destroys the writable layer; the inspect/config JSON in
  `/var/lib/docker/containers/<id>/` may survive but is not guaranteed.
  Collect early.
- Environment variables in inspect output often contain secrets; handle the
  JSON as sensitive and redact before sharing.
- Overlay2 directories are named by layer hash, not container name — map them
  via `docker inspect` (GraphDriver.Data) rather than guessing.
- Time skew between container logs (UTC) and host logs can mislead timelines;
  normalize to one timezone before correlating.

## References

- Docker docs: "dockerd storage" and `docker inspect` / `docker diff` references
  (docs.docker.com)
- MITRE ATT&CK: T1611 (Escape to Host), T1525 (Implant Internal Image),
  T1059 (Command and Scripting Interpreter)
- CIS Docker Benchmark (container runtime hardening guidance)
- NIST SP 800-190, Application Container Security Guide

---
*Original work authored for LEVI. Topic coverage inspired by github.com/mukul975/Anthropic-Cybersecurity-Skills; no content copied.*
