---
skill_id: sys_linux_ssh
name: Linux SSH
description: Secure remote access: keys, config, agents, and hardening.
risk: info
permissions: []
requires_confirmation: false
tags: [linux, security]
version: 1.0.0
---
# Linux SSH

## Purpose

Secure remote access: keys, config, agents, and hardening.

## Overview

SSH gives encrypted remote shells and file transfer. Key authentication beats passwords: ssh-keygen -t ed25519 creates a key pair; ssh-copy-id installs your public key on the server; the private key stays private with 600 permissions. Protect keys with a passphrase and load them into ssh-agent so you type it once per session (ssh-add). ~/.ssh/config simplifies life: Host aliases with HostName, User, Port, and IdentityFile - plus ProxyJump for hopping through bastions. scp and rsync -e ssh move files; ssh -L/-R forwards ports through the encrypted tunnel (local forward exposes a remote service locally). Server hardening: disable PasswordAuthentication and root login (PermitRootLogin no), move off port 22 or rate-limit with fail2ban, keep OpenSSH patched, and audit authorized_keys. Host key verification (known_hosts) defeats man-in-the-middle - never blindly accept changed host keys; investigate. Defensive habits: use keys everywhere, one key per device (revoke per device), and never paste private keys into chats, tickets, or repos.

## Quick reference

- ssh-keygen -t ed25519; ssh-copy-id user@host: key setup.

- Private keys 600, passphrase-protected, loaded via ssh-agent.

- ~/.ssh/config: Host aliases, IdentityFile, ProxyJump.

- scp/rsync over ssh for files; ssh -L/-R for port forwarding.

- Harden: no passwords, no root login, patched, fail2ban, audit authorized_keys.

- Never ignore changed host keys; never share private keys.


## Worked example

Key setup and everyday SSH patterns:

```
# One-time setup:
ssh-keygen -t ed25519 -C 'ada@laptop'
ssh-copy-id deploy@example.com

# ~/.ssh/config:
# Host prod
#   HostName 203.0.113.10
#   User deploy
#   IdentityFile ~/.ssh/id_ed25519

# Use:
ssh prod                       # via the alias
rsync -avz ./build/ prod:/srv/app/
ssh -L 8080:localhost:80 prod  # remote web admin on local :8080
```

- ed25519: modern, fast, compact keys.

- Config aliases turn long commands into `ssh prod`.

- -L forwards a remote port through the encrypted tunnel.


## Common mistakes

- Private key committed to a repo or pasted into a ticket.
  Fix: Rotate the key immediately; treat it as compromised.

- Disabling StrictHostKeyChecking globally to silence prompts.
  Fix: That removes MITM protection; verify keys properly instead.


## Quick checks

Q: Password or key auth - is there any contest?
A: No. Keys are phishing-resistant and automatable; passwords get brute-forced (watch auth logs). Disable password auth once keys work, and keep a console backup path before you do.


Q: The host key changed - proceed?
A: No, investigate first. Legitimate causes: server rebuild, key rotation. Attack cause: man-in-the-middle. Verify out-of-band with the server admin, then update known_hosts deliberately.


## Mental model

Key auth is a badge reader: your private key is the badge that never leaves your pocket, the server's authorized_keys is the reader that recognizes its public half. Passwords are shouting a secret across the lobby - anyone listening (brute-forcers) gets unlimited tries.
