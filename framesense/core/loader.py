"""只读图像加载：JPG/PNG/ARW → 统一 sRGB 空间。绝不修改原文件。"""

from __future__ import annotations

import hashlib
import io
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageOps

from framesense.core.color import convert_to_srgb

SUPPORTED_RASTER_EXTENSIONS = {".jpg", ".jpeg", ".png"}
SUPPORTED_RAW_EXTENSIONS = {".arw"}
SUPPORTED_EXTENSIONS = SUPPORTED_RASTER_EXTENSIONS | SUPPORTED_RAW_EXTENSIONS


@dataclass
class ImageData:
    """统一到 sRGB 的图像数据与来源元数据。"""

    rgb: np.ndarray
    width: int
    height: int
    source_path: str
    format: str
    colorspace: str = "sRGB"
    profile_source: str = "assumed"
    icc_error: str | None = None
    file_sha256: str = ""
    raw_meta: dict[str, Any] = field(default_factory=dict)
    preview_rgb: np.ndarray | None = None

    def __post_init__(self) -> None:
        if self.preview_rgb is None:
            self.preview_rgb = self.rgb


def validate_input_path(path: str | Path) -> Path:
    """校验输入路径存在且扩展名受支持。"""
    p = Path(path).expanduser().resolve()
    if not p.exists():
        raise FileNotFoundError(f"文件不存在: {p}")
    if not p.is_file():
        raise IsADirectoryError(f"不是文件: {p}")
    if p.suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise ValueError(
            f"不支持的图片格式: {p.suffix}（支持: {sorted(SUPPORTED_EXTENSIONS)}）"
        )
    return p


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_image_bytes(
    data: bytes,
    filename: str,
    source_label: str = "memory",
    *,
    max_side: int | None = None,
    preview_max_side: int = 1600,
) -> ImageData:
    """从内存字节加载图片（不落盘）。ARW 通过 rawpy 输出 sRGB。"""
    ext = Path(filename).suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"不支持的图片格式: {ext}")
    if max_side is not None and max_side < 1 or preview_max_side < 1:
        raise ValueError("预览与分析尺寸必须大于零")

    raw_meta: dict[str, Any] = {}
    if ext in SUPPORTED_RAW_EXTENSIONS:
        import rawpy

        try:
            with rawpy.imread(io.BytesIO(data)) as raw:
                # LibRaw honors camera orientation in postprocess. Half-size demosaic
                # bounds the expensive RAW stage; full editing remains external.
                original_w, original_h = int(raw.sizes.width), int(raw.sizes.height)
                if raw.sizes.flip in (5, 6):
                    original_w, original_h = original_h, original_w
                half_size = (
                    max_side is not None
                    and max(original_w, original_h)
                    > max(max_side, preview_max_side) * 2
                )
                rgb = raw.postprocess(
                    use_camera_wb=True,
                    output_bps=8,
                    no_auto_bright=False,
                    output_color=rawpy.ColorSpace.sRGB,
                    half_size=half_size,
                )
                raw_meta = {
                    "width": int(raw.sizes.width),
                    "height": int(raw.sizes.height),
                    "colors": int(raw.num_colors),
                    "half_size": half_size,
                }
            format_name = "RAW-ARW"
            profile_source = "rawpy_srgb"
            icc_error: str | None = None
        except Exception as exc:
            raise ValueError(
                f"RAW 文件解码失败（{type(exc).__name__}）：{exc}"
            ) from exc
    else:
        try:
            with Image.open(io.BytesIO(data)) as img:
                original_w, original_h = img.size
                if img.getexif().get(274) in (5, 6, 7, 8):
                    original_w, original_h = original_h, original_w
                format_name = (img.format or ext.lstrip(".")).upper()
                icc_profile = img.info.get("icc_profile")
                if max_side is not None:
                    decode_side = max(max_side, preview_max_side)
                    # JPEG decoder may decode at 1/2, 1/4 or 1/8 resolution.
                    img.draft("RGB", (decode_side, decode_side))
                oriented = ImageOps.exif_transpose(img)
                if max_side is not None:
                    oriented.thumbnail(
                        (decode_side, decode_side), Image.Resampling.LANCZOS
                    )
                converted, meta = convert_to_srgb(oriented, icc_profile)
                rgb = np.asarray(converted, dtype=np.uint8)
                profile_source = meta.get("profile_source", "assumed")
                icc_error = meta.get("icc_error")
        except Exception as exc:
            raise ValueError(f"图片解码失败（{type(exc).__name__}）：{exc}") from exc

    preview = make_preview(rgb, preview_max_side)
    if max_side is not None:
        rgb = make_preview(rgb, max_side)
    return ImageData(
        rgb=rgb,
        width=original_w,
        height=original_h,
        source_path=source_label,
        format=format_name,
        profile_source=profile_source,
        icc_error=icc_error,
        file_sha256=_sha256(data),
        raw_meta=raw_meta,
        preview_rgb=preview,
    )


def load_image(
    path: str | Path, *, max_side: int | None = None, preview_max_side: int = 1600
) -> ImageData:
    """从磁盘只读加载图片。"""
    p = validate_input_path(path)
    data = p.read_bytes()
    return load_image_bytes(
        data,
        p.name,
        source_label=str(p),
        max_side=max_side,
        preview_max_side=preview_max_side,
    )


def make_preview(rgb: np.ndarray, max_side: int = 1024) -> np.ndarray:
    """生成预览图（仅内存）。"""
    if max_side < 1:
        raise ValueError("预览尺寸必须大于零")
    h, w = rgb.shape[:2]
    scale = min(1.0, max_side / max(h, w))
    if scale >= 1.0:
        return rgb
    new_w, new_h = max(1, int(w * scale)), max(1, int(h * scale))
    return np.asarray(
        Image.fromarray(rgb).resize((new_w, new_h), Image.Resampling.LANCZOS),
        dtype=np.uint8,
    )
