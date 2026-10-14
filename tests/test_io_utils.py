"""输入输出工具测试。"""
from __future__ import annotations

from shutil import copyfile

import pytest

from framesense.features import validate_image_path
from framesense.io_utils import list_image_files, resolve_input


def test_list_single_file(sample_image):
    assert list_image_files(sample_image) == [sample_image.resolve()]


def test_list_directory_sorted(sample_frames, tmp_path):
    files = list_image_files(tmp_path)
    assert [f.name for f in files] == [f"frame_{i:03d}.png" for i in range(6)]


def test_list_directory_recursive(tmp_path, sample_frames):
    sub = tmp_path / "sub"
    sub.mkdir()
    extra = sub / "extra.png"
    copyfile(sample_frames[0], extra)
    files = list_image_files(tmp_path, recursive=True)
    assert any(f.name == "extra.png" for f in files)
    files_nonrecursive = list_image_files(tmp_path, recursive=False)
    assert not any(f.name == "extra.png" for f in files_nonrecursive)


def test_missing_path():
    with pytest.raises(FileNotFoundError):
        resolve_input("Z:/definitely_missing.png")


def test_unsupported_extension(tmp_path):
    p = tmp_path / "note.txt"
    p.write_text("hello", encoding="utf-8")
    with pytest.raises(ValueError):
        validate_image_path(p)
