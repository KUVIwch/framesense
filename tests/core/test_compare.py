"""双图对比测试。"""
from __future__ import annotations

import numpy as np
from PIL import Image

from framesense.core.compare import compare_images


def _rgb(size, color):
    return np.asarray(Image.new("RGB", size, color), dtype=np.uint8)


def test_identical_images_zero_difference():
    rgb = _rgb((32, 32), (120, 120, 120))
    cmp = compare_images(rgb, rgb)
    assert cmp.mean_lab_delta_e == 0.0
    assert cmp.histogram_distance == 0.0


def test_completely_different_images_large_difference():
    a = _rgb((32, 32), (20, 20, 20))
    b = _rgb((32, 32), (235, 235, 235))
    cmp = compare_images(a, b)
    assert cmp.mean_lab_delta_e > 20
    assert cmp.mean_luma_delta > 10


def test_brightness_difference_sign():
    a = _rgb((32, 32), (60, 60, 60))
    b = _rgb((32, 32), (180, 180, 180))
    cmp = compare_images(a, b)
    assert cmp.mean_luma_delta > 0
