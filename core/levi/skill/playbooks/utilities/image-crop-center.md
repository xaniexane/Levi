---
skill_id: utility.image_crop_center
name: Image Crop Center
description: Crop images from the center to a target size or aspect ratio.
risk: moderate
permissions: []
requires_confirmation: true
tags: [images, crop, batch]
version: 1.0.0
---

# Image Crop Center

Image Crop Center cuts each image down to your target dimensions by trimming evenly from the edges around the center point, then saves the cropped copy.

## When to use

- Squaring profile pictures from mixed photos.
- Cutting images to a fixed banner aspect ratio.
- Standardizing product shots to identical dimensions.

## Steps

1. Set the target width and height (or aspect ratio).
2. For each image, compute the centered crop box and cut.
3. Save cropped copies to the output folder with clear filenames.
4. Review a few results - center crop assumes the subject is centered.

## Honest limits

- Requires the third-party package Pillow (pip install Pillow).
- Cropping discards pixels permanently in the copy - the originals stay intact, which is why they stay.
- Off-center subjects get decapitated by center crop; check before batching.

Original work authored for LEVI - utilities pack.
