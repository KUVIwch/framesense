"""双图全局差异分析。"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from PIL import Image

from framesense.core.color import lab_delta_e, srgb_to_lab


@dataclass
class ImageComparison:
    """两张图像的全局差异。"""

    histogram_distance: float
    mean_lab_delta_e: float
    mean_luma_delta: float
    mean_chroma_delta: float
    mean_rgb_delta: list[float]
    note: str = ""


def _resize(rgb: np.ndarray, max_side: int = 256) -> np.ndarray:
    h, w = rgb.shape[:2]
    scale = min(1.0, max_side / max(h, w))
    if scale >= 1.0:
        return rgb
    new_w, new_h = max(1, int(w * scale)), max(1, int(h * scale))
    return np.asarray(
        Image.fromarray(rgb).resize((new_w, new_h), Image.Resampling.BILINEAR),
        dtype=np.uint8,
    )


def compare_images(rgb_a: np.ndarray, rgb_b: np.ndarray, max_side: int = 256) -> ImageComparison:
    """比较两张 sRGB 图像的全局差异（缩放到同一尺寸后计算）。"""
    a = _resize(rgb_a, max_side).astype(np.float32)
    b = _resize(rgb_b, max_side).astype(np.float32)
    gray_a = np.mean(a, axis=2)
    gray_b = np.mean(b, axis=2)
    ha, _ = np.histogram(gray_a, bins=256, range=(0, 256))
    hb, _ = np.histogram(gray_b, bins=256, range=(0, 256))
    ha = ha / (ha.sum() + 1e-9)
    hb = hb / (hb.sum() + 1e-9)
    hist_distance = float(np.sum(np.abs(ha - hb)) / 2.0)

    lab_a = srgb_to_lab(a.astype(np.uint8))
    lab_b = srgb_to_lab(b.astype(np.uint8))
    mean_de = lab_delta_e(lab_a, lab_b, method="CIE 1976")
    luma_delta = float(np.mean(lab_b[..., 0] - lab_a[..., 0]))
    chroma_a = np.sqrt(lab_a[..., 1] ** 2 + lab_a[..., 2] ** 2)
    chroma_b = np.sqrt(lab_b[..., 1] ** 2 + lab_b[..., 2] ** 2)
    chroma_delta = float(np.mean(chroma_b - chroma_a))
    mean_rgb_delta = [
        float(np.mean(b[..., c] - a[..., c]))
        for c in range(3)
    ]
    return ImageComparison(
        histogram_distance=round(hist_distance, 4),
        mean_lab_delta_e=round(mean_de, 3),
        mean_luma_delta=round(luma_delta, 3),
        mean_chroma_delta=round(chroma_delta, 3),
        mean_rgb_delta=[round(x, 3) for x in mean_rgb_delta],
    )
