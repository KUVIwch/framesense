"""图像只读加载测试。"""
from __future__ import annotations

import io
from pathlib import Path

import numpy as np
import pytest
from PIL import Image, ImageCms

from framesense.core.loader import (
    SUPPORTED_EXTENSIONS,
    load_image,
    load_image_bytes,
    make_preview,
    validate_input_path,
)


def _make_raster(path: Path, fmt: str = "PNG", icc: bool = False) -> None:
    img = Image.new("RGB", (32, 24), (120, 80, 200))
    kwargs = {}
    if icc:
        profile = ImageCms.createProfile("sRGB")
        kwargs["icc_profile"] = ImageCms.ImageCmsProfile(profile).tobytes()
    img.save(path, format=fmt, **kwargs)


def test_supported_extensions():
    assert {".jpg", ".jpeg", ".png", ".arw"} <= SUPPORTED_EXTENSIONS


def test_load_png_assumes_srgb(tmp_path):
    p = tmp_path / "a.png"
    _make_raster(p, "PNG")
    loaded = load_image(p)
    assert loaded.rgb.shape == (24, 32, 3)
    assert loaded.profile_source == "assumed"
    assert loaded.file_sha256


def test_load_jpg_with_icc(tmp_path):
    p = tmp_path / "a.jpg"
    _make_raster(p, "JPEG", icc=True)
    loaded = load_image(p)
    assert loaded.profile_source == "embedded"
    assert loaded.width == 32


def test_load_does_not_modify_original(tmp_path):
    p = tmp_path / "a.png"
    _make_raster(p, "PNG")
    before = p.read_bytes()
    load_image(p)
    assert p.read_bytes() == before


def test_load_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_image(tmp_path / "missing.png")


def test_load_unsupported_extension_raises(tmp_path):
    p = tmp_path / "note.txt"
    p.write_text("hello", encoding="utf-8")
    with pytest.raises(ValueError):
        validate_input_path(p)


def test_load_image_bytes_unsupported():
    with pytest.raises(ValueError):
        load_image_bytes(b"data", "x.gif")


def test_arw_invalid_bytes_raises():
    with pytest.raises(Exception):
        load_image_bytes(b"not-a-raw", "x.arw")


def test_make_preview_downscale():
    rgb = np.zeros((2000, 3000, 3), dtype=np.uint8)
    preview = make_preview(rgb, max_side=1024)
    assert preview.shape[1] == 1024


def test_make_preview_no_upscale():
    rgb = np.zeros((100, 100, 3), dtype=np.uint8)
    assert make_preview(rgb, max_side=1024).shape == (100, 100, 3)
