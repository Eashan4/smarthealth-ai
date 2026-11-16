# Unit 2: Biomedical Image Analysis -- Tutorials

Coursework for **21CSE428T Healthcare Analytics**, Unit 2 (T4/T5/T6). This
folder is separate from the main SmartHealth AI project (`backend/`, `ml/`,
`firmware/`, `dashboard/`) -- it is not part of the wearable app, it exists
only to satisfy the syllabus's hands-on-tutorial requirement.

## Why skimage sample images, not a project dataset

SmartHealth AI is an ESP32 + ML fall/activity-detection wearable. It ingests
motion (accelerometer/gyroscope) and PPG sensor time-series -- it has no
camera, no imaging pipeline, and no medical-image dataset anywhere in the
repo. Since Unit 2 requires image processing/analysis techniques, these
scripts use `skimage.data.cell()`, scikit-image's bundled fluorescence
microscopy cell image, as a biomedical-imaging stand-in. It ships with the
library (no network download, no external dataset needed) and is a real
grayscale microscopy image, which is representative enough for demonstrating
the required techniques (enhancement, restoration, segmentation,
compression, feature matching, CNN classification, visualization).

## One-time setup

The project venv (`/Users/eashanjain/Documents/Healthcare/venv`) already has
numpy, pandas, scikit-learn, torch, matplotlib, pillow, scipy. It is missing
`scikit-image`, which these scripts need for image I/O, filters,
segmentation, and feature detection. Install it once, additively -- the
root `requirements.txt` is untouched:

```bash
source /Users/eashanjain/Documents/Healthcare/venv/bin/activate
pip install -r tutorials/unit2_biomedical_imaging/requirements.txt
```

## Running the tutorials

Each script is independently runnable and self-checking (prints an
assert-based pass/fail at the end). Run from inside this directory:

```bash
source /Users/eashanjain/Documents/Healthcare/venv/bin/activate
cd tutorials/unit2_biomedical_imaging

python t4_enhancement_restoration_segmentation_compression.py
python t5_sift_ransac_cnn.py
python t6_visualization.py
```

All output images/plots are written to `outputs/`.

## T4 -- Biomedical Image Processing

`t4_enhancement_restoration_segmentation_compression.py`

| Technique | What it does | Key API |
|---|---|---|
| Enhancement | Global histogram equalization + CLAHE (adaptive local contrast) | `skimage.exposure.equalize_hist`, `equalize_adapthist` |
| Restoration | Adds synthetic Gaussian noise, then bilateral-filter denoises it, reports PSNR recovery | `skimage.util.random_noise`, `skimage.restoration.denoise_bilateral` |
| Segmentation | Otsu thresholding to isolate cell regions from background | `skimage.filters.threshold_otsu` |
| Compression | Saves the image as JPEG at quality 10/50/90, reports file size vs. PSNR vs. quality | `PIL.Image.save(format="JPEG")`, `skimage.metrics.peak_signal_noise_ratio` |

Sample result from a run: PSNR recovers from ~20.1 dB (noisy) to ~25.3 dB
(denoised); JPEG size grows from ~5.2 KB (q=10, 37.2 dB) to ~23.8 KB (q=90,
54.3 dB) -- the classic compression size/quality trade-off.

## T5 -- Biomedical Image Analysis Techniques (SIFT, RANSAC, CNN)

`t5_sift_ransac_cnn.py`

- **Feature detection**: uses `skimage.feature.SIFT`, which is present in
  this venv's scikit-image (0.24, >=0.19 required). The script still checks
  for it with a `try/except ImportError` and falls back to
  `skimage.feature.ORB` on older scikit-image installs where SIFT isn't
  available, so it keeps working either way.
- **RANSAC**: the sample image is warped with a known affine transform
  (12-degree rotation + translation) to create a second view. SIFT keypoints
  are detected and matched between the two views (loosened matching, i.e.
  `cross_check=False`, so a few wrong matches survive), then
  `skimage.measure.ransac` fits an `AffineTransform` and separates inlier
  matches (consistent with one global transform) from outliers. Both are
  visualized.
- **CNN**: a tiny 2-conv-layer torch CNN (`Conv2d -> ReLU -> MaxPool`, x2 ->
  `Linear`) is trained for 8 epochs on CPU. `torchvision` is **not**
  installed in this venv (checked with `pip show torchvision` before
  writing this), so instead of `torchvision.datasets`, the dataset is built
  from scratch with numpy/torch: random 32x32 patches cropped from the
  sample image (label 0) vs. the same patches rotated 90 degrees + flipped
  (label 1) -- a real, if toy, binary orientation-classification task. The
  script prints per-epoch loss and asserts the loss decreases.

## T6 -- Biomedical Image Visualization

`t6_visualization.py`

Builds three visualizations independently of T4 (recomputes CLAHE and the
Otsu mask itself so each script stays standalone per the assignment):

1. Side-by-side original vs. CLAHE-enhanced panels (`matplotlib` subplots)
2. Pixel-intensity histogram, original vs. enhanced, overlaid
3. Segmentation mask overlaid on the original as a red contour boundary
   (`skimage.measure.find_contours`)

## Output files

```
outputs/
  t4_original.png
  t4_enhancement_histeq.png
  t4_enhancement_clahe.png
  t4_restoration_noisy.png
  t4_restoration_denoised.png
  t4_segmentation_mask.png
  t4_compression_q10.jpg / q50.jpg / q90.jpg
  t5_keypoints.png
  t5_ransac_matches.png
  t5_cnn_patches.png
  t5_cnn_loss.png
  t6_side_by_side.png
  t6_histogram.png
  t6_segmentation_overlay.png
```
