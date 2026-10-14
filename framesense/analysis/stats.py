"""客观图像统计：亮度直方图、亮暗比例、色彩统计与清晰度代理。"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


@dataclass
class ImageStats:
    """单张图像的客观统计结果。"""

    width: int
    height: int
    histogram: list[int]
    histogram_normalized: list[float]
    percentiles: dict[str, float]
    shadow_ratio: float
    midtone_ratio: float
    highlight_ratio: float
    mean_brightness: float
    brightness_std: float
    contrast_rms: float
    mean_saturation: float
    mean_rgb: list[float]
    dominant_colors: list[dict]
    color_cast: dict[str, float]
    edge_density: float


def _gray(rgb: np.ndarray) -> np.ndarray:
    return np.mean(rgb.astype(np.float32), axis=2)


def compute_image_stats(rgb: np.ndarray) -> ImageStats:
    """计算图像客观统计。输入为 HxWx3 uint8 RGB 数组。"""
    if rgb.ndim != 3 or rgb.shape[2] != 3:
        raise ValueError(f"输入必须是 HxWx3 RGB 数组，当前 shape={rgb.shape}")
    rgb = rgb.astype(np.float32)
    gray = _gray(rgb)
    total = float(gray.size)
    if total == 0:
        raise ValueError("图像为空")

    hist, _ = np.histogram(gray, bins=256, range=(0, 256))
    hist_norm = hist / total

    percentiles = {
        str(p): float(np.percentile(gray, p))
        for p in [0, 5, 25, 50, 75, 95, 100]
    }

    shadow_ratio = float(np.mean(gray < 64))
    highlight_ratio = float(np.mean(gray > 192))
    midtone_ratio = float(np.mean((gray >= 64) & (gray <= 192)))

    mean_brightness = float(np.mean(gray))
    brightness_std = float(np.std(gray))
    contrast_rms = float(np.sqrt(np.mean((gray - mean_brightness) ** 2)))

    # 饱和度（手动 HSV 计算）
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    mx = np.maximum(np.maximum(r, g), b)
    mn = np.minimum(np.minimum(r, g), b)
    denom = np.maximum(mx + mn, 1e-6)
    sat = np.where(mx == mn, 0.0, (mx - mn) / denom)
    mean_saturation = float(np.mean(sat))

    mean_rgb = [float(np.mean(rgb[..., c])) for c in range(3)]
    color_cast = {
        "r_minus_g": round(mean_rgb[0] - mean_rgb[1], 2),
        "g_minus_b": round(mean_rgb[1] - mean_rgb[2], 2),
        "r_minus_b": round(mean_rgb[0] - mean_rgb[2], 2),
    }

    # 主色统计：32^3 量化 + bincount
    bins = 32
    q = (rgb // (256 // bins)).astype(np.int64)
    flat = q.reshape(-1, 3)
    idx = flat[:, 0] * (bins * bins) + flat[:, 1] * bins + flat[:, 2]
    counts = np.bincount(idx, minlength=bins**3).astype(np.float64)
    order = np.argsort(counts)[::-1][:5]
    color_counts = counts[order]
    color_sum = counts.sum()
    dominant_colors = []
    for ci, ccount in zip(order, color_counts):
        ci = int(ci)
        c0, c1, c2 = ci // (bins * bins), (ci // bins) % bins, ci % bins
        # 映射回中心值
        step = 256 // bins
        center = [int(c * step + step / 2) for c in (c0, c1, c2)]
        dominant_colors.append(
            {
                "rgb": center,
                "ratio": round(float(ccount) / float(color_sum), 4),
                "hex": "#{:02x}{:02x}{:02x}".format(center[0], center[1], center[2]),
            }
        )

    # 清晰度代理：梯度幅度均值
    gy, gx = np.gradient(gray)
    edge_density = float(np.mean(np.sqrt(gx**2 + gy**2)))

    return ImageStats(
        width=int(rgb.shape[1]),
        height=int(rgb.shape[0]),
        histogram=hist.astype(int).tolist(),
        histogram_normalized=hist_norm.tolist(),
        percentiles={k: round(v, 2) for k, v in percentiles.items()},
        shadow_ratio=round(shadow_ratio, 4),
        midtone_ratio=round(midtone_ratio, 4),
        highlight_ratio=round(highlight_ratio, 4),
        mean_brightness=round(mean_brightness, 2),
        brightness_std=round(brightness_std, 2),
        contrast_rms=round(contrast_rms, 2),
        mean_saturation=round(mean_saturation, 4),
        mean_rgb=[round(x, 2) for x in mean_rgb],
        dominant_colors=dominant_colors,
        color_cast=color_cast,
        edge_density=round(edge_density, 4),
    )
