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


def test_different_aspect_ratios_do_not_assume_pixel_correspondence():
    result = compare_images(
        _rgb((400, 100), (60, 80, 100)), _rgb((100, 300), (60, 80, 100))
    )
    assert result.mean_lab_delta_e == 0
    assert result.mean_luma_delta == 0
    assert result.histogram_distance == 0
    assert result.note


def test_scene_rearrangement_does_not_create_pixel_error():
    first = np.zeros((64, 64, 3), dtype=np.uint8)
    first[:, :32] = (200, 20, 20)
    first[:, 32:] = (20, 20, 200)
    result = compare_images(first, first[:, ::-1])
    assert result.mean_lab_delta_e == 0
    assert result.lab_distribution_distance == 0


def test_opposite_colors_do_not_disappear_in_distribution_metric():
    first = np.zeros((64, 64, 3), dtype=np.uint8)
    first[:, :32] = (220, 20, 20)
    first[:, 32:] = (20, 220, 220)
    second = _rgb((64, 64), (120, 120, 120))
    assert compare_images(first, second).lab_distribution_distance > 0.5
