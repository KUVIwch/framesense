"""色彩管理：ICC 读取/转换，Lab/OKLab 计算。

统一分析空间：sRGB。缺失 ICC 配置文件时按 sRGB 假设，并在元数据中标记。
"""
from __future__ import annotations

import io
from typing import Any

import numpy as np
from PIL import Image, ImageCms

WORKING_SPACE = "sRGB"


def srgb_to_rgb01(rgb: np.ndarray) -> np.ndarray:
    """uint8 RGB (HxWx3) -> 0-1 float RGB。"""
    return np.clip(rgb.astype(np.float32) / 255.0, 0.0, 1.0)


def srgb_to_lab(rgb: np.ndarray) -> np.ndarray:
    """sRGB (uint8 HxWx3) -> CIE Lab float (HxWx3)。"""
    import colour

    rgb01 = srgb_to_rgb01(rgb)
    xyz = colour.sRGB_to_XYZ(rgb01)
    return colour.XYZ_to_Lab(xyz)


def srgb_to_oklab(rgb: np.ndarray) -> np.ndarray:
    """sRGB (uint8 HxWx3) -> OKLab float (HxWx3)。"""
    import colour

    rgb01 = srgb_to_rgb01(rgb)
    xyz = colour.sRGB_to_XYZ(rgb01)
    return colour.XYZ_to_Oklab(xyz)


def lab_delta_e(lab_a: np.ndarray, lab_b: np.ndarray, method: str = "CIE 2000") -> float:
    """两组 Lab 数组的平均色差。"""
    import colour

    delta = colour.delta_E(lab_a, lab_b, method=method)
    return float(np.mean(delta))


def convert_to_srgb(
    image: Image.Image,
    icc_profile: bytes | None = None,
) -> tuple[Image.Image, dict[str, Any]]:
    """把图像转换到统一 sRGB 工作空间。

    Returns:
        (RGB Image, 元数据) —— profile_source 为 embedded/assumed，
        若 ICC 解析失败则回退假设 sRGB 并记录 icc_error。
    """
    if icc_profile is None:
        return image.convert("RGB"), {
            "colorspace": WORKING_SPACE,
            "profile_source": "assumed",
        }
    try:
        src_profile = ImageCms.getOpenProfile(io.BytesIO(icc_profile))
        dst_profile = ImageCms.createProfile("sRGB")
        converted = ImageCms.profileToProfile(
            image,
            src_profile,
            dst_profile,
            outputMode="RGB",
            renderingIntent=ImageCms.Intent.RELATIVE_COLORIMETRIC,
        )
        return converted, {
            "colorspace": WORKING_SPACE,
            "profile_source": "embedded",
        }
    except Exception as exc:
        return image.convert("RGB"), {
            "colorspace": WORKING_SPACE,
            "profile_source": "assumed",
            "icc_error": str(exc),
        }
