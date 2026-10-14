"""EXIF 读取测试。"""
from __future__ import annotations

import io
import json
from types import SimpleNamespace

import pytest
from PIL import Image

from framesense.analysis.exif import (
    ExifData,
    find_exiftool,
    read_exif,
    read_exif_bytes,
)


def _make_jpeg_with_exif(path) -> bytes:
    img = Image.new("RGB", (16, 16), (255, 0, 0))
    exif = Image.Exif()
    exif[0x010F] = "TestCamera"
    exif[0x0110] = "ModelX"
    exif[0x8827] = 400
    exif[0x829A] = (1, 250)  # ExposureTime
    exif[0x829D] = (28, 10)  # FNumber 2.8
    exif[0x920A] = (50, 1)  # FocalLength
    exif[0x9204] = (0, 1)  # ExposureBiasValue
    img.save(path, format="JPEG", exif=exif.tobytes())
    return path.read_bytes()


def test_read_exif_jpeg(tmp_path):
    p = tmp_path / "photo.jpg"
    _make_jpeg_with_exif(p)
    exif = read_exif(p)
    assert isinstance(exif, ExifData)
    assert exif.make == "TestCamera"
    assert exif.model == "ModelX"
    assert exif.iso == 400
    assert exif.aperture == pytest.approx(2.8, abs=0.01)
    assert exif.focal_length == pytest.approx(50.0, abs=0.01)
    assert exif.source in {"exifread", "exiftool"}


def test_read_exif_bytes(tmp_path):
    p = tmp_path / "photo.jpg"
    data = _make_jpeg_with_exif(p)
    exif = read_exif_bytes(data, "photo.jpg")
    assert exif.iso == 400
    assert exif.aperture == pytest.approx(2.8, abs=0.01)


def test_missing_exif_returns_none(tmp_path):
    p = tmp_path / "plain.png"
    Image.new("RGB", (8, 8), (10, 20, 30)).save(p, format="PNG")
    exif = read_exif(p)
    assert exif.make is None
    assert exif.model is None
    assert exif.iso is None
    assert exif.aperture is None
    assert exif.source in {"exifread", "exiftool"}


def test_exiftool_reader(monkeypatch, tmp_path):
    p = tmp_path / "photo.jpg"
    _make_jpeg_with_exif(p)
    fake_json = json.dumps(
        [
            {
                "Make": "Sony",
                "Model": "ILCE-7M4",
                "ISO": 640,
                "Aperture": 2.8,
                "FNumber": 2.8,
                "FocalLength": 35.0,
                "ExposureTime": 0.004,
                "ShutterSpeed": "1/250",
                "ExposureCompensation": -0.3,
                "WhiteBalance": "Auto",
                "LensModel": "FE 35mm F1.8",
                "DateTimeOriginal": "2026:10:13 10:00:00",
                "Orientation": 1,
            }
        ]
    )

    def fake_run(cmd, capture_output=True, timeout=30):
        return SimpleNamespace(returncode=0, stdout=fake_json.encode("utf-8"))

    monkeypatch.setattr("framesense.analysis.exif.subprocess.run", fake_run)
    monkeypatch.setattr("framesense.analysis.exif.find_exiftool", lambda: "exiftool")
    exif = read_exif(p)
    assert exif.source == "exiftool"
    assert exif.make == "Sony"
    assert exif.iso == 640
    assert exif.aperture == pytest.approx(2.8, abs=0.01)
    assert exif.exposure_bias == pytest.approx(-0.3, abs=0.01)
    assert exif.lens_model == "FE 35mm F1.8"


def test_exiftool_failure_falls_back(tmp_path, monkeypatch):
    p = tmp_path / "photo.jpg"
    _make_jpeg_with_exif(p)

    def fake_run(cmd, capture_output=True, timeout=30):
        return SimpleNamespace(returncode=1, stdout=b"")

    monkeypatch.setattr("framesense.analysis.exif.subprocess.run", fake_run)
    monkeypatch.setattr("framesense.analysis.exif.find_exiftool", lambda: "exiftool")
    exif = read_exif(p)
    assert exif.source == "exifread"
    assert exif.iso == 400


def test_find_exiftool_returns_none_when_absent(monkeypatch):
    monkeypatch.setattr("framesense.analysis.exif.shutil.which", lambda name: None)
    monkeypatch.setattr("framesense.analysis.exif.TOOLS_EXIFTOOL", __import__("pathlib").Path("Z:/nonexistent/tools/exiftool.exe"))
    assert find_exiftool() is None
