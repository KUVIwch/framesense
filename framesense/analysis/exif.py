"""EXIF 读取。

优先使用 ExifTool（若系统中存在或位于项目 .tools/ 目录），否则回退到 exifread。
绝不编造缺失的 EXIF 参数：读取不到的字段一律为 None。
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import exifread

from framesense.analysis.loader import SUPPORTED_EXTENSIONS, validate_input_path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
TOOLS_EXIFTOOL = PROJECT_ROOT / ".tools" / ("exiftool.exe" if os.name == "nt" else "exiftool")


@dataclass
class ExifData:
    """可用的 EXIF 字段；缺失字段一律为 None。"""

    make: str | None = None
    model: str | None = None
    iso: int | None = None
    shutter_speed: str | None = None
    aperture: float | None = None
    focal_length: float | None = None
    exposure_bias: float | None = None
    white_balance: str | None = None
    lens_model: str | None = None
    taken_at: str | None = None
    orientation: int | None = None
    source: str = "none"
    raw_tags: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """转为可 JSON 序列化字典（不含原始大字段）。"""
        return {
            "make": self.make,
            "model": self.model,
            "iso": self.iso,
            "shutter_speed": self.shutter_speed,
            "aperture": self.aperture,
            "focal_length": self.focal_length,
            "exposure_bias": self.exposure_bias,
            "white_balance": self.white_balance,
            "lens_model": self.lens_model,
            "taken_at": self.taken_at,
            "orientation": self.orientation,
            "source": self.source,
        }


def find_exiftool() -> str | None:
    """查找可用的 ExifTool 可执行文件。"""
    candidates: list[str] = [str(TOOLS_EXIFTOOL)]
    which = shutil.which("exiftool")
    if which:
        candidates.append(which)
    for c in candidates:
        if c and Path(c).is_file():
            return c
    return None


def read_exif(path: str | Path) -> ExifData:
    """从磁盘文件读取 EXIF。"""
    p = validate_input_path(path)
    tool = find_exiftool()
    if tool:
        data = _read_with_exiftool(tool, p)
        if data is not None:
            return data
    return _read_exifread_path(p)


def read_exif_bytes(data: bytes, filename: str) -> ExifData:
    """从内存字节读取 EXIF（用于 Web 上传）。"""
    ext = Path(filename).suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"不支持的图片格式: {ext}")
    return _read_exifread_bytes(data)


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _to_int(value: Any) -> int | None:
    try:
        if value is None or value == "":
            return None
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _to_float(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _read_with_exiftool(exiftool_path: str, path: Path) -> ExifData | None:
    """调用 ExifTool 读取 EXIF（-n 输出数值）。"""
    cmd = [exiftool_path, "-json", "-fast", "-n", str(path)]
    try:
        proc = subprocess.run(cmd, capture_output=True, timeout=30)
    except Exception:
        return None
    if proc.returncode != 0:
        return None
    try:
        rows = json.loads(proc.stdout.decode("utf-8", errors="replace"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
    if not rows:
        return None
    tag = rows[0]
    return ExifData(
        make=_clean(tag.get("Make")),
        model=_clean(tag.get("Model")),
        iso=_to_int(tag.get("ISO")) or _to_int(tag.get("PhotographicSensitivity")),
        shutter_speed=_clean(tag.get("ShutterSpeed")) or _shutter_from_seconds(_to_float(tag.get("ExposureTime"))),
        aperture=_to_float(tag.get("Aperture")) or _to_float(tag.get("FNumber")),
        focal_length=_to_float(tag.get("FocalLength")),
        exposure_bias=_to_float(tag.get("ExposureCompensation")),
        white_balance=_clean(tag.get("WhiteBalance")),
        lens_model=_clean(tag.get("LensModel")),
        taken_at=_clean(tag.get("DateTimeOriginal")),
        orientation=_to_int(tag.get("Orientation")),
        source="exiftool",
        raw_tags=_pick_tags(tag),
    )


def _pick_tags(tag: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "Make",
        "Model",
        "ISO",
        "ShutterSpeed",
        "ExposureTime",
        "Aperture",
        "FNumber",
        "FocalLength",
        "ExposureCompensation",
        "WhiteBalance",
        "LensModel",
        "DateTimeOriginal",
        "Orientation",
        "ImageWidth",
        "ImageHeight",
    ]
    return {k: tag.get(k) for k in keys if tag.get(k) is not None}


def _shutter_from_seconds(seconds: float | None) -> str | None:
    if seconds is None or seconds <= 0:
        return None
    if seconds >= 1:
        return f"{seconds:.1f}s"
    return f"1/{int(round(1.0 / seconds))}"


def _read_exifread_path(path: Path) -> ExifData:
    with open(path, "rb") as f:
        return _parse_exifread(exifread.process_file(f, details=False))


def _read_exifread_bytes(data: bytes) -> ExifData:
    import io

    return _parse_exifread(exifread.process_file(io.BytesIO(data), details=False))


def _tag_str(tags: dict[str, Any], *names: str) -> str | None:
    for name in names:
        tag = tags.get(name)
        if tag is not None:
            text = str(tag.printable).strip()
            return text or None
    return None


def _tag_float(tags: dict[str, Any], *names: str) -> float | None:
    for name in names:
        tag = tags.get(name)
        if tag is None or not hasattr(tag, "values"):
            continue
        try:
            vals = list(tag.values)
            if len(vals) >= 2 and float(vals[1]) != 0:
                return float(vals[0]) / float(vals[1])
            if len(vals) >= 1:
                return float(vals[0])
        except (TypeError, ValueError, ZeroDivisionError):
            continue
    return None


def _shutter_str_from_float(value: float | None) -> str | None:
    if value is None:
        return None
    return _shutter_from_seconds(value)


def _parse_exifread(tags: dict[str, Any]) -> ExifData:
    iso = (
        _to_int(_tag_str(tags, "EXIF PhotographicSensitivity", "Image PhotographicSensitivity"))
        or _to_int(_tag_str(tags, "EXIF ISOSpeedRatings", "Image ISOSpeedRatings"))
    )
    aperture_raw = _tag_float(tags, "EXIF FNumber", "Image FNumber")
    return ExifData(
        make=_tag_str(tags, "Image Make", "EXIF Make"),
        model=_tag_str(tags, "Image Model", "EXIF Model"),
        iso=iso,
        shutter_speed=_shutter_str_from_float(_tag_float(tags, "EXIF ExposureTime", "Image ExposureTime")),
        aperture=aperture_raw,
        focal_length=_tag_float(tags, "EXIF FocalLength", "Image FocalLength"),
        exposure_bias=_tag_float(tags, "EXIF ExposureBiasValue", "Image ExposureBiasValue"),
        white_balance=_tag_str(tags, "EXIF WhiteBalance", "Image WhiteBalance"),
        lens_model=_tag_str(tags, "EXIF LensModel", "Image LensModel"),
        taken_at=_tag_str(tags, "EXIF DateTimeOriginal", "Image DateTimeOriginal"),
        orientation=_to_int(_tag_str(tags, "Image Orientation", "EXIF Orientation")),
        source="exifread",
        raw_tags={
            "make": _tag_str(tags, "Image Make", "EXIF Make"),
            "model": _tag_str(tags, "Image Model", "EXIF Model"),
            "iso": _tag_str(tags, "EXIF PhotographicSensitivity", "Image PhotographicSensitivity", "EXIF ISOSpeedRatings", "Image ISOSpeedRatings"),
            "exposure_time": _tag_str(tags, "EXIF ExposureTime", "Image ExposureTime"),
            "fnumber": _tag_str(tags, "EXIF FNumber", "Image FNumber"),
            "focal_length": _tag_str(tags, "EXIF FocalLength", "Image FocalLength"),
            "exposure_bias": _tag_str(tags, "EXIF ExposureBiasValue", "Image ExposureBiasValue"),
            "white_balance": _tag_str(tags, "EXIF WhiteBalance", "Image WhiteBalance"),
            "lens_model": _tag_str(tags, "EXIF LensModel", "Image LensModel"),
            "taken_at": _tag_str(tags, "EXIF DateTimeOriginal", "Image DateTimeOriginal"),
            "orientation": _tag_str(tags, "Image Orientation", "EXIF Orientation"),
        },
    )
