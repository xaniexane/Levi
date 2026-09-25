---
skill_id: utility.base64_encode_decode
name: Base64 Encode Decode
description: Encode text to base64 or decode base64 back to text, with validation.
risk: info
permissions: []
requires_confirmation: false
tags: [base64, encoding, text]
version: 1.0.0
---

# Base64 Encode Decode

Base64 Encode/Decode converts between plain text and base64 in either direction, validating input on decode and reporting errors plainly. Display only - nothing is stored.

## When to use

- Encoding binary-ish data for a text-only channel.
- Decoding a base64 blob to see what it holds.
- Preparing credentials for HTTP Basic auth headers.

## Steps

1. For encoding: take UTF-8 text, encode with base64, display the result.
2. For decoding: validate the input strictly (validate=True); on binascii.Error, report it instead of guessing.
3. Decode to UTF-8 text and display; note when the bytes are not valid UTF-8.
4. Keep it in the terminal - encoded secrets are still secrets.

## Honest limits

- Standard library only (base64).
- Base64 is encoding, NOT encryption - it hides nothing from anyone.
- URL-safe vs standard alphabet matters; confirm which one your counterpart expects.

Original work authored for LEVI - utilities pack.
