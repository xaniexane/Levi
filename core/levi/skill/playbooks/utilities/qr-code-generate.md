---
skill_id: utility.qr_code_generate
name: QR Code Generate
description: Generate a QR code PNG from text or a URL using a third-party QR library.
risk: moderate
permissions: []
requires_confirmation: true
tags: [qr, code, generate, images]
version: 1.0.0
---

# QR Code Generate

QR Code Generate encodes your text or URL into a QR code image and writes it to a PNG file, sized for reliable scanning.

## When to use

- Encoding a Wi-Fi join or URL into a scannable code.
- Making a QR for a payment or contact card.
- Printing a link onto physical material.

## Steps

1. Install a QR library (qrcode or segno - pip install qrcode).
2. Build the payload: URLs verbatim, text as UTF-8.
3. Generate at error-correction level M or higher and a box size that scans (10+ for print).
4. Write the PNG to a new file.
5. Verify by scanning it with a phone before publishing.

## Honest limits

- Requires a third-party QR package - the standard library has no QR encoder.
- QR capacity is finite: long payloads need lower error correction or a bigger symbol - check before printing.
- Always scan-test the output; an unscanned QR is a rumor.

Original work authored for LEVI - utilities pack.
