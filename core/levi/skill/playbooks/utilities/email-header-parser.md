---
skill_id: utility.email_header_parser
name: Email Header Parser
description: Parse email headers and display From, To, Date, Subject, and the Received chain.
risk: info
permissions: []
requires_confirmation: false
tags: [email, headers, parse]
version: 1.0.0
---

# Email Header Parser

Email Header Parser reads a raw email message and lays out its headers plainly: who it claims to be from, the date, subject, and the Received hops in order. Display only - it makes no trust judgments.

## When to use

- Inspecting a suspicious message's claimed origin.
- Reading the relay path of a delayed email.
- Extracting metadata from a saved .eml file.

## Steps

1. Parse the raw message with the email package (policy.default).
2. Extract From, To, Cc, Date, Subject, and Message-ID.
3. Walk the Received headers top-to-bottom into a chronological hop list.
4. Display everything plainly; flag missing or malformed Date headers.

## Honest limits

- Standard library only (email).
- Headers are forgeable - this skill displays claims, it does not authenticate them.
- For authentication verdicts you need SPF/DKIM/DMARC checks, which is separate work.

Original work authored for LEVI - utilities pack.
