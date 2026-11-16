"""T4: Biomedical Image Processing -- enhancement, restoration, segmentation,
compression. Course: 21CSE428T Healthcare Analytics, Unit 2.

Sample image: skimage.data.cell() (a fluorescence microscopy cell image,
bundled with scikit-image, no download needed) stands in for a biomedical
image -- SmartHealth AI itself has no imaging pipeline, see tutorials/
unit2_biomedical_imaging/README.md for why this dataset was chosen.

Usage: python t4_enhancement_restoration_segmentation_compression.py
"""

from __future__ import annotations

import io
from pathlib import Path

import numpy as np
from PIL import Image
from skimage import data, exposure, filters, restoration, util
from skimage.metrics import peak_signal_noise_ratio as psnr

OUT = Path(__file__).parent / "outputs"


def save_png(img: np.ndarray, name: str) -> Path:
    """Save a float [0,1] or uint8 array as a PNG under outputs/."""
    path = OUT / name
    arr = img
    if arr.dtype != np.uint8:
        arr = util.img_as_ubyte(np.clip(arr, 0, 1))
    Image.fromarray(arr).save(path)
    return path


def enhancement(image: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Global histogram equalization and CLAHE (adaptive, local contrast)."""
    equalized = exposure.equalize_hist(image)
    clahe = exposure.equalize_adapthist(image, clip_limit=0.03)
    save_png(equalized, "t4_enhancement_histeq.png")
    save_png(clahe, "t4_enhancement_clahe.png")
    return equalized, clahe


def restoration_demo(image: np.ndarray) -> tuple[np.ndarray, np.ndarray, float, float]:
    """Add synthetic Gaussian noise, then denoise, and show the PSNR recovery."""
    image_f = util.img_as_float(image)
    noisy = util.random_noise(image_f, mode="gaussian", var=0.01, rng=0)
    denoised = restoration.denoise_bilateral(noisy, sigma_color=0.1, sigma_spatial=5)

    psnr_noisy = psnr(image_f, noisy, data_range=1.0)
    psnr_denoised = psnr(image_f, denoised, data_range=1.0)

    save_png(noisy, "t4_restoration_noisy.png")
    save_png(denoised, "t4_restoration_denoised.png")
    return noisy, denoised, psnr_noisy, psnr_denoised


def segmentation(image: np.ndarray) -> np.ndarray:
    """Otsu thresholding to isolate cell regions from background."""
    thresh = filters.threshold_otsu(image)
    mask = image > thresh
    save_png(mask.astype(np.uint8) * 255, "t4_segmentation_mask.png")
    return mask


def compression(image: np.ndarray) -> dict[int, dict[str, float]]:
    """Save as JPEG at a few quality levels and report size vs. PSNR."""
    pil_img = Image.fromarray(image)
    image_f = util.img_as_float(image)
    results = {}
    for quality in (10, 50, 90):
        buf = io.BytesIO()
        pil_img.save(buf, format="JPEG", quality=quality)
        size_kb = len(buf.getvalue()) / 1024
        out_path = OUT / f"t4_compression_q{quality}.jpg"
        out_path.write_bytes(buf.getvalue())

        decoded = np.array(Image.open(io.BytesIO(buf.getvalue())))
        quality_psnr = psnr(image_f, util.img_as_float(decoded), data_range=1.0)
        results[quality] = {"size_kb": size_kb, "psnr_db": quality_psnr}
    return results


def main():
    OUT.mkdir(exist_ok=True)
    image = data.cell()  # uint8 grayscale, bundled sample microscopy image
    save_png(image, "t4_original.png")

    equalized, clahe = enhancement(image)
    noisy, denoised, psnr_noisy, psnr_denoised = restoration_demo(image)
    mask = segmentation(image)
    comp = compression(image)

    print("Enhancement: saved histogram-equalized and CLAHE images.")
    print(f"Restoration: PSNR noisy={psnr_noisy:.2f} dB -> denoised={psnr_denoised:.2f} dB")
    print(f"Segmentation: Otsu mask covers {mask.mean() * 100:.1f}% of pixels as foreground")
    print("Compression (quality -> size_kb, PSNR dB):")
    for q, r in comp.items():
        print(f"  q={q}: {r['size_kb']:.1f} KB, {r['psnr_db']:.2f} dB")

    # --- self-check ---
    expected_files = [
        "t4_original.png", "t4_enhancement_histeq.png", "t4_enhancement_clahe.png",
        "t4_restoration_noisy.png", "t4_restoration_denoised.png",
        "t4_segmentation_mask.png",
        "t4_compression_q10.jpg", "t4_compression_q50.jpg", "t4_compression_q90.jpg",
    ]
    for fname in expected_files:
        fpath = OUT / fname
        assert fpath.exists() and fpath.stat().st_size > 0, f"missing or empty output: {fname}"

    assert psnr_denoised > psnr_noisy, "denoising should improve PSNR over the noisy image"
    assert 0.0 < mask.mean() < 1.0, "Otsu mask should not be all-foreground or all-background"
    assert comp[10]["size_kb"] < comp[90]["size_kb"], "higher JPEG quality should mean larger file"
    assert comp[10]["psnr_db"] < comp[90]["psnr_db"], "higher JPEG quality should mean higher PSNR"
    print("\nT4 self-check passed.")


if __name__ == "__main__":
    main()
