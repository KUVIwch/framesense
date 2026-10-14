"""图像统计测试。"""
from __future__ import annotations

import numpy as np
import pytest
from PIL import Image

from framesense.core.stats import compute_image_stats


def _rgb(size, color):
    return np.asarray(Image.new("RGB", size, color), dtype=np.uint8)


def test_black_image():
    stats = compute_image_stats(_rgb((16, 16), (0, 0, 0)))
    assert stats.mean_brightness == pytest.approx(0, abs=1)
    assert stats.shadow_ratio == pytest.approx(1.0, abs=0.01)
    assert stats.highlight_ratio == pytest.approx(0.0, abs=0.01)
    assert len(stats.histogram) == 256
    assert abs(sum(stats.histogram_normalized) - 1.0) < 1e-6


def test_white_image():
    stats = compute_image_stats(_rgb((16, 16), (255, 255, 255)))
    assert stats.highlight_ratio == pytest.approx(1.0, abs=0.01)
    assert stats.mean_brightness == pytest.approx(255, abs=1)


def test_low_saturation_image():
    stats = compute_image_stats(_rgb((16, 16), (120, 120, 120)))
    assert stats.mean_saturation < 0.05
    assert stats.mean_chroma < 1.0


def test_checkerboard_contrast_and_edge():
    arr = np.zeros((32, 32, 3), dtype=np.uint8)
    arr[::2, ::2] = 255
    arr[1::2, 1::2] = 255
    stats = compute_image_stats(arr)
    assert stats.contrast_rms > 50
    assert stats.edge_density > 0


def test_solid_color_dominant_colors():
    stats = compute_image_stats(_rgb((16, 16), (200, 100, 50)))
    assert stats.dominant_colors[0]["ratio"] > 0.9
    assert stats.dominant_colors[0]["hex"].startswith("#")


def test_highlight_shadow_tint():
    img = np.zeros((32, 32, 3), dtype=np.uint8)
    img[:16, :] = (250, 230, 200)  # 上部暖色高光（亮度 >192）
    img[16:, :] = (10, 60, 10)      # 下部深绿暗部（亮度 <64）
    stats = compute_image_stats(img)
    assert stats.highlight_tint_lab["a"] > 0
    assert stats.shadow_tint_lab["a"] < 0


def test_invalid_input_shape():
    with pytest.raises(ValueError):
        compute_image_stats(np.zeros((10, 10, 4), dtype=np.uint8))
