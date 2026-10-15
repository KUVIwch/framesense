"""色彩管理测试。"""

from __future__ import annotations

import io

import numpy as np
import pytest
from PIL import Image, ImageCms

from framesense.core.color import convert_to_srgb, srgb_to_lab, srgb_to_oklab


def test_srgb_to_lab_red():
    rgb = np.array([[[255, 0, 0]]], dtype=np.uint8)
    lab = srgb_to_lab(rgb)
    assert lab[0, 0, 0] == pytest.approx(53.24, abs=0.5)
    assert lab[0, 0, 1] == pytest.approx(80.1, abs=0.5)
    assert lab[0, 0, 2] == pytest.approx(67.2, abs=0.5)


def test_srgb_to_oklab_red():
    rgb = np.array([[[255, 0, 0]]], dtype=np.uint8)
    oklab = srgb_to_oklab(rgb)
    assert oklab[0, 0, 0] == pytest.approx(0.6279, abs=0.01)
    assert oklab[0, 0, 1] == pytest.approx(0.2249, abs=0.01)


def test_convert_without_icc_assumes_srgb():
    img = Image.new("RGB", (8, 8), (200, 100, 50))
    converted, meta = convert_to_srgb(img, icc_profile=None)
    assert meta["profile_source"] == "assumed"
    assert converted.mode == "RGB"


def test_convert_with_embedded_icc():
    profile = ImageCms.createProfile("sRGB")
    icc_bytes = ImageCms.ImageCmsProfile(profile).tobytes()
    img = Image.new("RGB", (8, 8), (200, 100, 50))
    converted, meta = convert_to_srgb(img, icc_profile=icc_bytes)
    assert meta["profile_source"] == "embedded"
    assert converted.size == (8, 8)


def test_convert_with_invalid_icc_falls_back():
    converted, meta = convert_to_srgb(
        Image.new("RGB", (4, 4)), icc_profile=b"not-an-icc"
    )
    assert meta["profile_source"] == "assumed"
    assert "icc_error" in meta


def test_non_srgb_lab_profile_is_actually_transformed():
    # Encoded LAB (128,128,128) is a neutral ~50 L* gray; blindly treating the
    # input bytes as RGB would yield 128 instead of the profile transform.
    profile = ImageCms.ImageCmsProfile(ImageCms.createProfile("LAB")).tobytes()
    image = Image.new("LAB", (8, 8), (128, 128, 128))
    converted, meta = convert_to_srgb(image, profile)
    pixel = converted.getpixel((0, 0))
    assert meta["profile_source"] == "embedded"
    assert max(pixel) - min(pixel) <= 2
    assert 115 <= pixel[0] <= 123
