"""本地图像特征提取（只读，绝不写回原图）。"""
from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
from PIL import Image

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".webp", ".tif", ".tiff", ".gif"}
COMPARE_SIZE = (128, 128)
HIST_BINS = 128


def validate_image_path(path: str | Path) -> Path:
    """校验图片路径存在且扩展名受支持。"""
    p = Path(path).expanduser().resolve()
    if not p.exists():
        raise FileNotFoundError(f"文件不存在: {p}")
    if not p.is_file():
        raise IsADirectoryError(f"不是文件: {p}")
    if p.suffix.lower() not in IMAGE_EXTENSIONS:
        raise ValueError(f"不支持的图片格式: {p.suffix}（支持: {sorted(IMAGE_EXTENSIONS)}）")
    return p


def load_image(path: str | Path) -> Image.Image:
    """只读加载图片，返回 RGB 副本用于分析，绝不修改原文件。"""
    p = validate_image_path(path)
    with Image.open(p) as img:
        img.load()
        return img.convert("RGB")


def file_size_bytes(path: str | Path) -> int:
    """返回原文件字节数。"""
    return Path(path).expanduser().resolve().stat().st_size


def _to_array(img: Image.Image) -> np.ndarray:
    """转 RGB float32 数组。"""
    return np.asarray(img.convert("RGB"), dtype=np.float32)


def mean_brightness(img: Image.Image) -> float:
    """图像平均亮度（0~255）。"""
    return float(np.mean(_to_array(img)))


def brightness_std(img: Image.Image) -> float:
    """图像亮度标准差。"""
    return float(np.std(_to_array(img)))


def mean_saturation(img: Image.Image) -> float:
    """图像平均饱和度（0~1）。"""
    rgb = np.asarray(img.convert("RGB"), dtype=np.float32)
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    mx = np.maximum(np.maximum(r, g), b)
    mn = np.minimum(np.minimum(r, g), b)
    denom = np.maximum(mx + mn, 1e-6)
    sat = np.where(mx == mn, 0.0, (mx - mn) / denom)
    return float(np.mean(sat))


def unique_colors(img: Image.Image, sample_limit: int = 200_000) -> int:
    """统计去重颜色数；超大图先采样以控制内存。"""
    rgb = np.asarray(img.convert("RGB"))
    if rgb.size > sample_limit:
        step = max(1, int(np.sqrt(rgb.shape[0] * rgb.shape[1] / 200_000)) + 1)
        rgb = rgb[::step, ::step]
    return int(np.unique(rgb.reshape(-1, 3), axis=0).shape[0])


def luminance_histogram(img: Image.Image, bins: int = HIST_BINS) -> list[float]:
    """归一化亮度直方图。"""
    gray = np.asarray(img.convert("L"), dtype=np.float32).ravel()
    hist, _ = np.histogram(gray, bins=bins, range=(0, 256))
    total = float(hist.sum())
    if total == 0:
        return [0.0] * bins
    return (hist / total).tolist()


def normalized_rgb_histogram(img: Image.Image, bins: int = 32) -> list[float]:
    """32^3 归一化 RGB 直方图，用于颜色距离计算。"""
    rgb = np.asarray(img.convert("RGB"), dtype=np.uint8)
    q = (rgb // (256 // bins)).astype(np.int64)
    flat = q.reshape(-1, 3)
    idx = flat[:, 0] * (bins * bins) + flat[:, 1] * bins + flat[:, 2]
    hist = np.bincount(idx, minlength=bins**3).astype(np.float64)
    total = float(hist.sum())
    if total == 0:
        return [0.0] * (bins**3)
    return (hist / total).tolist()


def _resize_for_compare(img: Image.Image) -> Image.Image:
    """统一缩放用于帧间比较。"""
    return img.convert("RGB").resize(COMPARE_SIZE, Image.Resampling.BILINEAR)


def compute_pair_diff(img_a: Image.Image, img_b: Image.Image) -> dict[str, float]:
    """计算相邻帧差异：MAE、RMSE、直方图距离与综合差异分（0~1）。"""
    a = _to_array(_resize_for_compare(img_a))
    b = _to_array(_resize_for_compare(img_b))
    diff = np.abs(a - b)
    mae = float(np.mean(diff))
    rmse = float(np.sqrt(np.mean(diff**2)))

    hist_a = np.asarray(_resize_for_compare(img_a).convert("L"), dtype=np.float32).ravel()
    hist_b = np.asarray(_resize_for_compare(img_b).convert("L"), dtype=np.float32).ravel()
    ha, _ = np.histogram(hist_a, bins=HIST_BINS, range=(0, 256))
    hb, _ = np.histogram(hist_b, bins=HIST_BINS, range=(0, 256))
    ha = ha / (ha.sum() + 1e-9)
    hb = hb / (hb.sum() + 1e-9)
    hist_dist = float(np.sum(np.abs(ha - hb)) / 2.0)

    mae_norm = mae / 255.0
    diff_score = float(np.clip(0.6 * mae_norm + 0.4 * hist_dist, 0.0, 1.0))
    return {
        "mae": mae,
        "rmse": rmse,
        "histogram_distance": hist_dist,
        "diff_score": diff_score,
    }


def sha256_of_file(path: str | Path) -> str:
    """计算原图 SHA-256，用于校验原图未被修改。"""
    p = validate_image_path(path)
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()
