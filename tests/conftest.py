"""共享测试夹具：创建临时演示图片。"""
from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image, ImageDraw


def make_frame(path: Path, index: int, size: tuple[int, int] = (64, 48)) -> None:
    """绘制一张带移动圆形的合成帧。"""
    width, height = size
    img = Image.new("RGB", size, (30, 30, 40))
    draw = ImageDraw.Draw(img)
    cx = int(width * (0.2 + 0.6 * index / 5))
    cy = int(height * 0.5)
    r = int(height * 0.2)
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(200, 100, 180))
    img.save(path, format="PNG")


@pytest.fixture
def sample_frames(tmp_path: Path) -> list[Path]:
    """生成 6 张内容变化的演示帧。"""
    paths = []
    for i in range(6):
        p = tmp_path / f"frame_{i:03d}.png"
        make_frame(p, i)
        paths.append(p)
    return paths


@pytest.fixture
def sample_image(tmp_path: Path) -> Path:
    """生成单张演示图片。"""
    p = tmp_path / "single.png"
    make_frame(p, 0)
    return p
