---
skill_id: utility.image_resize_batch
name: Image Resize Batch
description: Resize a batch of images to a max dimension, keeping aspect ratio, into an output folder.
risk: moderate
permissions: []
requires_confirmation: true
tags: [images, resize, batch]
version: 1.0.0
---

# Image Resize Batch

Image Resize Batch scales every image you point it at so the longest side fits your target size, preserving aspect ratio, and saves the results into a separate output folder. Originals are never overwritten.

## When to use

- Preparing photos for web upload at a sane size.
- Standardizing a folder of mixed images to thumbnails.
- Shrinking screenshots before attaching them.

## Steps

1. Gather the input images and confirm the target size (longest side in pixels).
2. For each image, apply EXIF transpose first so phone photos are upright, then resize with high-quality resampling.
3. Save each result into the output folder with the same filename; choose JPEG quality or PNG as fits.
4. Verify one output visually and confirm dimensions before treating the batch as done.

## Honest limits

- Requires the third-party package Pillow (pip install Pillow).
- Downscaling is safe; upscaling invents no detail - it only makes pixels bigger.
- Resizing is lossy for JPEG: always work from originals, never re-resize a resized copy.

Original work authored for LEVI - utilities pack.
