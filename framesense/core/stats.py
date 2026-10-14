"""客观图像统计（统一 sRGB 空间内计算）。"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from PIL import Image

from framesense.core.color import srgb_to_lab


@dataclass
class ImageStats:
    """单张图像的客观统计。"""

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
    mean_chroma: float
    mean_rgb: list[float]
    dominant_colors: list[dict]
    highlight_tint_lab: dict[str, float]
    shadow_tint_lab: dict[str, float]
    color_cast_lab: dict[str, float]
    edge_density: float


def _gray(rgb: np.ndarray) -> np.ndarray:
    return np.mean(rgb.astype(np.float32), axis=2)


def _downscale(rgb: np.ndarray, max_side: int = 512) -> np.ndarray:
    h, w = rgb.shape[:2]
    if max(h, w) <= max_side:
        return rgb
    scale = max_side / max(h, w)
    new_w, new_h = max(1, int(w * scale)), max(1, int(h * scale))
    return np.asarray(
        Image.fromarray(rgb).resize((new_w, new_h), Image.Resampling.BILINEAR),
        dtype=np.uint8,
    )


def _dominant_colors(rgb: np.ndarray, top: int = 5, bins: int = 32) -> list[dict]:
    small = _downscale(rgb, max_side=256)
    step = 256 // bins
    q = (small // step).astype(np.int64)
    flat = q.reshape(-1, 3)
    idx = flat[:, 0] * (bins * bins) + flat[:, 1] * bins + flat[:, 2]
    counts = np.bincount(idx, minlength=bins**3).astype(np.float64)
    order = np.argsort(counts)[::-1][:top]
    total = counts.sum()
    result = []
    for ci in order:
        ci = int(ci)
        c0, c1, c2 = ci // (bins * bins), (ci // bins) % bins, ci % bins
        center = [int(c * step + step / 2) for c in (c0, c1, c2)]
        result.append(
            {
                "rgb": center,
                "ratio": round(float(counts[ci]) / float(total), 4),
                "hex": "#{:02x}{:02x}{:02x}".format(center[0], center[1], center[2]),
            }
        )
    return result


def _mean_tint(lab: np.ndarray, mask: np.ndarray) -> dict[str, float]:
    if not np.any(mask):
        return {"a": 0.0, "b": 0.0}
    return {
        "a": float(np.mean(lab[..., 1][mask])),
        "b": float(np.mean(lab[..., 2][mask])),
    }


def compute_image_stats(rgb: np.ndarray) -> ImageStats:
    """计算图像客观统计。输入 HxWx3 uint8 sRGB。"""
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

    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    mx = np.maximum(np.maximum(r, g), b)
    mn = np.minimum(np.minimum(r, g), b)
    denom = np.maximum(mx + mn, 1e-6)
    sat = np.where(mx == mn, 0.0, (mx - mn) / denom)
    mean_saturation = float(np.mean(sat))
    mean_rgb = [float(np.mean(rgb[..., c])) for c in range(3)]

    small = _downscale(rgb.astype(np.uint8), max_side=512)
    lab = srgb_to_lab(small)
    mean_chroma = float(np.mean(np.sqrt(lab[..., 1] ** 2 + lab[..., 2] ** 2)))
    small_gray = _gray(small.astype(np.float32))
    shadow_mask = small_gray < 64
    highlight_mask = small_gray > 192
    shadow_tint = _mean_tint(lab, shadow_mask)
    highlight_tint = _mean_tint(lab, highlight_mask)
    color_cast = {
        "a": float(np.mean(lab[..., 1])),
        "b": float(np.mean(lab[..., 2])),
    }

    dominant = _dominant_colors(rgb.astype(np.uint8))
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
        mean_chroma=round(mean_chroma, 4),
        mean_rgb=[round(x, 2) for x in mean_rgb],
        dominant_colors=dominant,
        highlight_tint_lab={k: round(v, 3) for k, v in highlight_tint.items()},
        shadow_tint_lab={k: round(v, 3) for k, v in shadow_tint.items()},
        color_cast_lab={k: round(v, 3) for k, v in color_cast.items()},
        edge_density=round(edge_density, 4),
    )
