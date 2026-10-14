"""区域选择与区域差异测试。"""
from __future__ import annotations

import numpy as np
import pytest
from PIL import Image

from framesense.core.regions import (
    Region,
    clamp_region,
    compute_region_stats,
    region_difference,
    validate_region,
)


def _rgb(size, color):
    return np.asarray(Image.new("RGB", size, color), dtype=np.uint8)


def test_clamp_region_out_of_bounds():
    r = clamp_region(Region(x=-5, y=0, width=100, height=100), (48, 64))
    assert r.x >= 0
    assert r.x + r.width <= 64
    assert r.y + r.height <= 48


def test_validate_empty_region_raises():
    with pytest.raises(ValueError):
        validate_region(Region(x=0, y=0, width=0, height=10), (100, 100))


def test_validate_tiny_region_raises():
    with pytest.raises(ValueError):
        validate_region(Region(x=0, y=0, width=1, height=1), (100, 100), min_pixels=4)


def test_region_stats_mean_color():
    rgb = _rgb((64, 64), (10, 20, 30))
    stats = compute_region_stats(rgb, Region(x=0, y=0, width=64, height=64))
    assert stats.mean_rgb[0] == pytest.approx(10, abs=1)
    assert stats.mean_rgb[1] == pytest.approx(20, abs=1)
    assert stats.mean_rgb[2] == pytest.approx(30, abs=1)
    assert stats.pixel_count == 64 * 64


def test_region_difference_detects_color_change():
    rgb_a = _rgb((32, 32), (200, 50, 50))
    rgb_b = _rgb((32, 32), (50, 200, 50))
    region = Region(x=0, y=0, width=32, height=32)
    stats_a = compute_region_stats(rgb_a, region)
    stats_b = compute_region_stats(rgb_b, region)
    diff = region_difference(stats_a, stats_b)
    assert diff["delta_e_cie76"] > 20
    assert abs(diff["a_delta"]) > 10
    assert abs(diff["b_delta"]) > 10


def test_region_difference_same_region_zero():
    rgb = _rgb((32, 32), (100, 100, 100))
    region = Region(x=0, y=0, width=32, height=32)
    stats = compute_region_stats(rgb, region)
    diff = region_difference(stats, stats)
    assert diff["delta_e_cie76"] == pytest.approx(0, abs=0.01)
    assert diff["luma_delta"] == pytest.approx(0, abs=0.01)
