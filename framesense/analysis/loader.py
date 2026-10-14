"""只读加载 JPG/PNG/Sony ARW 图像。

设计约束：
- 图像以只读方式打开，处理结果仅存在于内存，绝不写回原文件。
- RAW 默认只在本地处理（内存中解码），不自动上传。
"""
from __future__ import annotations

import hashlib
import io
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

SUPPORTED_RASTER_EXTENSIONS = {".jpg", ".jpeg", ".png"}
SUPPORTED_RAW_EXTENSIONS = {".arw"}
SUPPORTED_EXTENSIONS = SUPPORTED_RASTER_EXTENSIONS | SUPPORTED_RAW_EXTENSIONS


@dataclass
class LoadedImage:
    """内存中的图像数据与来源元数据。"""

    rgb: np.ndarray  # HxWx3 uint8
    width: int
    height: int
    source_path: str
    format: str
    raw_meta: dict[str, Any] = field(default_factory=dict)
    file_sha256: str = ""


def validate_input_path(path: str | Path) -> Path:
    """校验输入路径存在且扩展名受支持。"""
    p = Path(path).expanduser().resolve()
    if not p.exists():
        raise FileNotFoundError(f"文件不存在: {p}")
    if not p.is_file():
        raise IsADirectoryError(f"不是文件: {p}")
    if p.suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"不支持的图片格式: {p.suffix}（支持: {sorted(SUPPORTED_EXTENSIONS)}）")
    return p


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_image_bytes(data: bytes, filename: str, source_label: str = "memory") -> LoadedImage:
    """从内存字节加载图片（用于 Web 上传，不落盘）。

    Args:
        data: 图片文件字节。
        filename: 原始文件名（用于判断扩展名）。
        source_label: 来源标签（如上传文件名）。
    """
    ext = Path(filename).suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"不支持的图片格式: {ext}（支持: {sorted(SUPPORTED_EXTENSIONS)}）")

    raw_meta: dict[str, Any] = {}
    if ext in SUPPORTED_RAW_EXTENSIONS:
        import rawpy

        try:
            with rawpy.imread(io.BytesIO(data)) as raw:
                rgb = raw.postprocess(use_camera_wb=True, output_bps=8, no_auto_bright=False)
                raw_meta = {
                    "width": int(raw.sizes.width),
                    "height": int(raw.sizes.height),
                    "colors": int(raw.num_colors),
                    "black_level": int(raw.black_level) if raw.black_level is not None else None,
                    "white_level": int(raw.white_level) if raw.white_level is not None else None,
                    "camera_wb": [float(x) for x in raw.camera_whitebalance]
                    if raw.camera_whitebalance is not None
                    else None,
                }
        except Exception as exc:
            raise ValueError(f"RAW 文件解码失败（{type(exc).__name__}）：{exc}") from exc
        format_name = "RAW-ARW"
    else:
        try:
            with Image.open(io.BytesIO(data)) as img:
                img.load()
                rgb = np.asarray(img.convert("RGB"), dtype=np.uint8)
                format_name = (img.format or ext.lstrip(".")).upper()
        except Exception as exc:
            raise ValueError(f"图片解码失败（{type(exc).__name__}）：{exc}") from exc

    h, w = rgb.shape[:2]
    return LoadedImage(
        rgb=rgb,
        width=w,
        height=h,
        source_path=source_label,
        format=format_name,
        raw_meta=raw_meta,
        file_sha256=_sha256(data),
    )


def load_image(path: str | Path) -> LoadedImage:
    """从磁盘只读加载图片，不修改原文件。"""
    p = validate_input_path(path)
    data = p.read_bytes()
    return load_image_bytes(data, p.name, source_label=str(p))


def make_preview(rgb: np.ndarray, max_side: int = 1024) -> np.ndarray:
    """生成用于云端分析的缩小预览图（仅内存，不落盘）。"""
    h, w = rgb.shape[:2]
    scale = min(1.0, max_side / max(h, w))
    if scale >= 1.0:
        return rgb
    new_w, new_h = max(1, int(w * scale)), max(1, int(h * scale))
    return np.asarray(
        Image.fromarray(rgb).resize((new_w, new_h), Image.Resampling.LANCZOS),
        dtype=np.uint8,
    )
