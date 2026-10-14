"""输入路径解析与只读加载。"""
from __future__ import annotations

from pathlib import Path

from framesense.features import IMAGE_EXTENSIONS, validate_image_path


def resolve_input(path: str | Path) -> Path:
    """解析并校验输入路径存在。"""
    p = Path(path).expanduser().resolve()
    if not p.exists():
        raise FileNotFoundError(f"路径不存在: {p}")
    return p


def list_image_files(path: str | Path, recursive: bool = False) -> list[Path]:
    """列出图片文件；若输入为文件则只返回该文件，若为目录则按文件名排序。"""
    p = resolve_input(path)
    if p.is_file():
        validate_image_path(p)
        return [p]
    if p.is_dir():
        iterator = p.rglob("*") if recursive else p.glob("*")
        files = sorted(
            (f for f in iterator if f.is_file() and f.suffix.lower() in IMAGE_EXTENSIONS),
            key=lambda f: f.name,
        )
        return files
    raise NotADirectoryError(f"既不是文件也不是目录: {p}")
