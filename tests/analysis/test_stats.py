"""图像统计测试。"""
from __future__ import annotations

import numpy as np
import pytest
from PIL import Image

from framesense.analysis.stats import compute_image_stats


def _rgb(size, color):
    return np.asarray(Image.new("RGB", size, color), dtype=np.uint8)


def test_black_image_stats():
    rgb = _rgb((16, 16), (0, 0, 0))
    stats = compute_image_stats(rgb)
    assert stats.width == 16
    assert stats.height == 16
    assert stats.mean_brightness == pytest.approx(0, abs=1)
    assert stats.shadow_ratio == pytest.approx(1.0, abs=0.01)
    assert stats.highlight_ratio == pytest.approx(0.0, abs=0.01)
    assert abs(sum(stats.histogram_normalized) - 1.0) < 1e-6
    assert len(stats.histogram) == 256


def test_white_image_stats():
    rgb = _rgb((16, 16), (255, 255, 255))
    stats = compute_image_stats(rgb)
    assert stats.mean_brightness == pytest.approx(255, abs=1)
    assert stats.highlight_ratio == pytest.approx(1.0, abs=0.01)
    assert stats.shadow_ratio == pytest.approx(0.0, abs=0.01)


def test_checkerboard_contrast_and_edge():
    arr = np.zeros((32, 32, 3), dtype=np.uint8)
    arr[::2, ::2] = 255
    arr[1::2, 1::2] = 255
    stats = compute_image_stats(arr)
    assert stats.contrast_rms > 50
    assert stats.edge_density > 0
    assert stats.brightness_std > 50


def test_solid_color_dominant_colors():
    rgb = _rgb((16, 16), (200, 100, 50))
    stats = compute_image_stats(rgb)
    assert stats.dominant_colors
    top = stats.dominant_colors[0]
    assert top["ratio"] > 0.9
    assert top["hex"].startswith("#")


def test_invalid_input_shape():
    with pytest.raises(ValueError):
        compute_image_stats(np.zeros((10, 10, 4), dtype=np.uint8))


def test_mean_rgb_and_color_cast():
    rgb = _rgb((16, 16), (100, 120, 140))
    stats = compute_image_stats(rgb)
    assert stats.mean_rgb[0] == pytest.approx(100, abs=1)
    assert stats.mean_rgb[1] == pytest.approx(120, abs=1)
    assert stats.mean_rgb[2] == pytest.approx(140, abs=1)
    assert stats.color_cast["r_minus_g"] == pytest.approx(-20, abs=2)
    assert stats.color_cast["g_minus_b"] == pytest.approx(-20, abs=2)
