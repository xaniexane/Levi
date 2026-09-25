---
skill_id: utility.image_convert_webp
name: Image Convert WebP
description: Convert images to the WebP format for smaller files at similar quality.
risk: moderate
permissions: []
requires_confirmation: true
tags: [images, webp, convert]
version: 1.0.0
---

# Image Convert WebP

Image Convert WebP re-encodes images (JPEG, PNG, and others) into WebP, which typically cuts file size substantially at the same visual quality. Outputs go to new files.

## When to use

- Slimming down images for a website.
- Converting a PNG-heavy asset folder to modern formats.
- Reducing attachment sizes without visible quality loss.

## Steps

1. Confirm each input opens and note whether it has transparency.
2. Convert color mode as needed (WebP handles RGB and RGBA).
3. Save with quality around 80 as a starting point, method 6 for better compression if time allows.
4. Compare input and output file sizes and spot-check the image visually.

## Honest limits

- Requires Pillow built with WebP support - verify with PIL.features.check('webp') before batching.
- Animated images are not handled by this skill; stills only.
- Quality 80 is a starting point, not a law - text-heavy images may want higher.

Original work authored for LEVI - utilities pack.
