"""图像只读加载测试。"""
from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from framesense.analysis.loader import (
    SUPPORTED_EXTENSIONS,
    load_image,
    load_image_bytes,
    make_preview,
    validate_input_path,
)


def _make_raster(path: Path, fmt: str = "PNG") -> None:
    img = Image.new("RGB", (32, 24), (120, 80, 200))
    img.save(path, format=fmt)


def test_supported_extensions_include_required():
    assert {".jpg", ".jpeg", ".png", ".arw"} <= SUPPORTED_EXTENSIONS


def test_load_png(tmp_path):
    p = tmp_path / "a.png"
    _make_raster(p, "PNG")
    loaded = load_image(p)
    assert loaded.width == 32
    assert loaded.height == 24
    assert loaded.rgb.shape == (24, 32, 3)
    assert loaded.format == "PNG"
    assert loaded.file_sha256


def test_load_jpg(tmp_path):
    p = tmp_path / "a.jpg"
    _make_raster(p, "JPEG")
    loaded = load_image(p)
    assert loaded.rgb.shape == (24, 32, 3)
    assert loaded.format in {"JPEG", "JPG"}


def test_load_image_does_not_modify_original(tmp_path):
    p = tmp_path / "a.png"
    _make_raster(p, "PNG")
    before = p.read_bytes()
    load_image(p)
    after = p.read_bytes()
    assert before == after


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


def test_make_preview_downscale():
    import numpy as np

    rgb = np.zeros((2000, 3000, 3), dtype=np.uint8)
    preview = make_preview(rgb, max_side=1024)
    assert preview.shape[1] == 1024
    assert preview.shape[0] == 682


def test_make_preview_no_upscale():
    import numpy as np

    rgb = np.zeros((100, 100, 3), dtype=np.uint8)
    preview = make_preview(rgb, max_side=1024)
    assert preview.shape == (100, 100, 3)
