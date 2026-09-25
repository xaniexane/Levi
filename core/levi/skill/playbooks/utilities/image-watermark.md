---
skill_id: utility.image_watermark
name: Image Watermark
description: Overlay a text or image watermark onto pictures and save watermarked copies.
risk: moderate
permissions: []
requires_confirmation: true
tags: [images, watermark, branding]
version: 1.0.0
---

# Image Watermark

Image Watermark composites a semi-transparent text stamp or logo image onto each picture - corner or tiled - and saves the result as a new file.

## When to use

- Branding portfolio images before sharing.
- Marking proofs so they cannot be used as finals.
- Stamping a copyright notice across a batch.

## Steps

1. Prepare the watermark: text (font, size) or a logo image with transparency.
2. Choose placement (a corner, or tiled) and an opacity that marks without ruining.
3. Composite the watermark layer over each image and save to new files.
4. Inspect one result at full size: legible stamp, image still usable.

## Honest limits

- Requires the third-party package Pillow (pip install Pillow).
- The watermark is baked into the pixels - keep unwatermarked originals separately.
- A watermark deters casual reuse; it does not survive a determined crop.

Original work authored for LEVI - utilities pack.
