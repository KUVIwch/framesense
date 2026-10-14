"""矩形区域选择与区域统计。"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from framesense.core.color import srgb_to_lab


@dataclass(frozen=True)
class Region:
    """图像中的矩形区域（绝对像素坐标）。"""

    x: int
    y: int
    width: int
    height: int


def clamp_region(region: Region, image_shape: tuple[int, int]) -> Region:
    """把区域限制在图像边界内。"""
    height, width = image_shape[:2]
    x = max(0, min(region.x, width - 1))
    y = max(0, min(region.y, height - 1))
    x2 = max(x, min(region.x + region.width, width))
    y2 = max(y, min(region.y + region.height, height))
    return Region(x, y, x2 - x, y2 - y)


def validate_region(region: Region, image_shape: tuple[int, int], min_pixels: int = 4) -> Region:
    """校验并规范化区域：越界裁剪、空区域/过小区域抛错。"""
    r = clamp_region(region, image_shape)
    if r.width <= 0 or r.height <= 0:
        raise ValueError(f"区域为空: {r}")
    if r.width * r.height < min_pixels:
        raise ValueError(f"区域像素数过少: {r.width * r.height} < {min_pixels}")
    return r


@dataclass
class RegionStats:
    """区域统计结果。"""

    region: Region
    pixel_count: int
    mean_rgb: list[float]
    mean_lab: list[float]
    mean_luma: float
    mean_chroma: float
    dominant_colors: list[dict]


def compute_region_stats(rgb: np.ndarray, region: Region) -> RegionStats:
    """计算矩形区域的颜色与明暗统计。"""
    r = validate_region(region, rgb.shape)
    patch = rgb[r.y : r.y + r.height, r.x : r.x + r.width].astype(np.float32)
    lab = srgb_to_lab(patch.astype(np.uint8))
    mean_lab = [
        float(np.mean(lab[..., 0])),
        float(np.mean(lab[..., 1])),
        float(np.mean(lab[..., 2])),
    ]
    mean_rgb = [float(np.mean(patch[..., c])) for c in range(3)]
    return RegionStats(
        region=r,
        pixel_count=int(patch.shape[0] * patch.shape[1]),
        mean_rgb=mean_rgb,
        mean_lab=mean_lab,
        mean_luma=mean_lab[0],
        mean_chroma=float(np.sqrt(mean_lab[1] ** 2 + mean_lab[2] ** 2)),
        dominant_colors=_dominant_colors(patch.astype(np.uint8)),
    )


def _dominant_colors(rgb: np.ndarray, top: int = 3, bins: int = 32) -> list[dict]:
    from framesense.core.stats import _dominant_colors as _dc

    return _dc(rgb, top=top, bins=bins)


def region_difference(stats_a: RegionStats, stats_b: RegionStats) -> dict:
    """计算两个对应区域的差异指标（基于区域均值）。"""
    import colour

    lab_a = np.array([stats_a.mean_lab], dtype=np.float64)
    lab_b = np.array([stats_b.mean_lab], dtype=np.float64)
    de76 = float(np.mean(colour.delta_E(lab_a, lab_b, method="CIE 1976")))
    de2000 = float(np.mean(colour.delta_E(lab_a, lab_b, method="CIE 2000")))
    return {
        "delta_e_cie76": round(de76, 3),
        "delta_e_cie2000": round(de2000, 3),
        "luma_delta": round(stats_b.mean_luma - stats_a.mean_luma, 3),
        "chroma_delta": round(stats_b.mean_chroma - stats_a.mean_chroma, 3),
        "a_delta": round(stats_b.mean_lab[1] - stats_a.mean_lab[1], 3),
        "b_delta": round(stats_b.mean_lab[2] - stats_a.mean_lab[2], 3),
    }
