"""Markdown 报告导出测试。"""
from __future__ import annotations

import numpy as np

from framesense.analysis.exif import ExifData
from framesense.analysis.stats import compute_image_stats
from framesense.export import build_markdown_report, export_markdown
from framesense.grading.decision import generate_suggestion
from framesense.grading.models import IntentInput


def _stats():
    rgb = np.full((32, 32, 3), 120, dtype=np.uint8)
    return compute_image_stats(rgb)


def test_build_markdown_report_contains_sections():
    exif = ExifData(make="Sony", model="ILCE-7M4", iso=400, source="exifread")
    intent = IntentInput(keywords=["电影感"])
    plan = generate_suggestion(stats=_stats(), exif=exif, intent=intent, client=None)
    md = build_markdown_report("photo.jpg", exif, _stats(), intent, plan)
    assert "# FrameSense" in md
    assert "photo.jpg" in md
    assert "Sony" in md
    assert "ISO" in md and "400" in md
    assert "客观图像统计" in md
    assert "调色方案" in md
    assert "不应破坏的艺术特征" in md
    assert "Mock" in md


def test_build_markdown_report_no_exif_does_not_fabricate():
    exif = ExifData()
    intent = IntentInput(keywords=["清新"])
    plan = generate_suggestion(stats=_stats(), exif=exif, intent=intent, client=None)
    md = build_markdown_report("photo.png", exif, _stats(), intent, plan)
    assert "未读取到 EXIF" in md
    assert "ISO" not in md


def test_export_markdown_writes_file(tmp_path):
    intent = IntentInput(keywords=["温暖"])
    plan = generate_suggestion(stats=_stats(), exif=ExifData(), intent=intent, client=None)
    out = export_markdown(
        "photo.jpg",
        ExifData(),
        _stats(),
        intent,
        plan,
        tmp_path / "reports" / "report.md",
    )
    assert out.exists()
    assert out.read_text(encoding="utf-8").startswith("# FrameSense")
