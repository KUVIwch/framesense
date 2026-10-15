"""双图全局差异分析。"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from PIL import Image

from framesense.core.color import lab_delta_e, srgb_to_lab
from framesense.core.stats import _gray


@dataclass
class ImageComparison:
    """两张图像的全局差异。"""

    histogram_distance: float
    mean_lab_delta_e: float
    mean_luma_delta: float
    mean_chroma_delta: float
    mean_rgb_delta: list[float]
    note: str = ""
    mean_lab_delta_e_2000: float = 0.0
    lab_distribution_distance: float = 0.0


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


def compare_images(
    rgb_a: np.ndarray, rgb_b: np.ndarray, max_side: int = 256
) -> ImageComparison:
    """Compare distributions and mean colors, without assuming pixel alignment.

    ``mean_lab_delta_e`` is CIE76 between the two *mean Lab vectors*. It is
    not a mean of corresponding pixel errors or an overall imitation score.
    """
    if max_side < 1:
        raise ValueError("比较尺寸必须大于零")
    for rgb in (rgb_a, rgb_b):
        if rgb.ndim != 3 or rgb.shape[2] != 3 or not rgb.shape[0] or not rgb.shape[1]:
            raise ValueError("输入必须是非空 HxWx3 RGB 数组")
    a = _resize(rgb_a, max_side).astype(np.float32)
    b = _resize(rgb_b, max_side).astype(np.float32)
    gray_a = _gray(a)
    gray_b = _gray(b)
    ha, _ = np.histogram(gray_a, bins=256, range=(0, 256))
    hb, _ = np.histogram(gray_b, bins=256, range=(0, 256))
    ha = ha / (ha.sum() + 1e-9)
    hb = hb / (hb.sum() + 1e-9)
    hist_distance = float(np.sum(np.abs(ha - hb)) / 2.0)

    lab_a = srgb_to_lab(a.astype(np.uint8))
    lab_b = srgb_to_lab(b.astype(np.uint8))
    mean_a = np.mean(lab_a, axis=(0, 1))
    mean_b = np.mean(lab_b, axis=(0, 1))
    mean_de = lab_delta_e(mean_a, mean_b, method="CIE 1976")
    mean_de00 = lab_delta_e(mean_a, mean_b, method="CIE 2000")
    luma_delta = float(mean_b[0] - mean_a[0])
    chroma_a = np.sqrt(lab_a[..., 1] ** 2 + lab_a[..., 2] ** 2)
    chroma_b = np.sqrt(lab_b[..., 1] ** 2 + lab_b[..., 2] ** 2)
    chroma_delta = float(np.mean(chroma_b) - np.mean(chroma_a))
    mean_rgb_delta = [float(np.mean(b[..., c]) - np.mean(a[..., c])) for c in range(3)]
    # Coarse Lab occupancy adds a distribution check when mean colors cancel.
    ranges = ((0, 100.001), (-128, 128), (-128, 128))
    histogram_a = np.histogramdd(lab_a.reshape(-1, 3), bins=(10, 16, 16), range=ranges)[
        0
    ]
    histogram_b = np.histogramdd(lab_b.reshape(-1, 3), bins=(10, 16, 16), range=ranges)[
        0
    ]
    distribution_distance = (
        np.sum(
            np.abs(histogram_a / histogram_a.sum() - histogram_b / histogram_b.sum())
        )
        / 2
    )
    return ImageComparison(
        histogram_distance=round(hist_distance, 4),
        mean_lab_delta_e=round(mean_de, 3),
        mean_luma_delta=round(luma_delta, 3),
        mean_chroma_delta=round(chroma_delta, 3),
        mean_rgb_delta=[round(x, 3) for x in mean_rgb_delta],
        mean_lab_delta_e_2000=round(mean_de00, 3),
        lab_distribution_distance=round(float(distribution_distance), 4),
        note="ΔE 为全图平均 Lab 色的距离；直方图与 Lab 分布比较不要求像素对齐。场景、构图和物体占比会影响数值，不能作为仿色成绩。差值方向：原片减参考图。",
    )
