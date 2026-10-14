"""图像特征提取测试。"""
from __future__ import annotations

import pytest
from PIL import Image, ImageDraw

from framesense.features import (
    brightness_std,
    compute_pair_diff,
    load_image,
    luminance_histogram,
    mean_brightness,
    mean_saturation,
    unique_colors,
)


def test_load_image_rgb(sample_image):
    img = load_image(sample_image)
    assert img.mode == "RGB"
    assert img.size == (64, 48)


def test_mean_brightness_range(sample_image):
    img = load_image(sample_image)
    assert 0 <= mean_brightness(img) <= 255


def test_brightness_std_nonnegative(sample_image):
    img = load_image(sample_image)
    assert brightness_std(img) >= 0


def test_mean_saturation_range(sample_image):
    img = load_image(sample_image)
    assert 0 <= mean_saturation(img) <= 1


def test_unique_colors_positive(sample_image):
    img = load_image(sample_image)
    assert unique_colors(img) > 1


def test_luminance_histogram_normalized(sample_image):
    img = load_image(sample_image)
    hist = luminance_histogram(img)
    assert len(hist) == 128
    assert abs(sum(hist) - 1.0) < 1e-6


def test_pair_diff_same_image(sample_image):
    img = load_image(sample_image)
    d = compute_pair_diff(img, img)
    assert d["mae"] == pytest.approx(0, abs=0.01)
    assert d["diff_score"] == pytest.approx(0, abs=0.01)


def test_pair_diff_different():
    """两张内容明显不同的图片应得到显著大于 0 的差异分。"""
    img_a = Image.new("RGB", (64, 48), (20, 20, 20))
    draw_a = ImageDraw.Draw(img_a)
    draw_a.ellipse([10, 10, 30, 30], fill=(220, 220, 220))
    img_b = Image.new("RGB", (64, 48), (235, 235, 235))
    draw_b = ImageDraw.Draw(img_b)
    draw_b.rectangle([20, 15, 50, 35], fill=(40, 40, 40))
    d = compute_pair_diff(img_a, img_b)
    assert d["diff_score"] > 0.1
