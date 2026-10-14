"""报告生成与保存测试。"""
from __future__ import annotations

import json

from framesense.ai.mock import MockAnalyzer
from framesense.analyzer import analyze_sequence
from framesense.report import save_json, save_markdown, to_markdown


def test_save_json_roundtrip(sample_frames, tmp_path):
    report = analyze_sequence(
        sample_frames,
        ai_analyzer=MockAnalyzer(),
        threshold=0.2,
        ai_mode="mock",
    )
    out = save_json(report, tmp_path / "report.json")
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["total_frames"] == 6
    assert data["frames"][0]["ai"]["provider"] == "mock"


def test_markdown_contains_key_sections(sample_frames):
    report = analyze_sequence(
        sample_frames,
        ai_analyzer=MockAnalyzer(),
        threshold=0.2,
        ai_mode="mock",
    )
    md = to_markdown(report)
    assert "# FrameSense" in md
    assert "帧详情" in md
    assert "帧间差异" in md


def test_save_markdown_nested_dir(tmp_path, sample_frames):
    report = analyze_sequence(
        sample_frames,
        ai_analyzer=MockAnalyzer(),
        threshold=0.2,
        ai_mode="mock",
    )
    out = save_markdown(report, tmp_path / "sub" / "report.md")
    assert out.exists()
    assert out.parent.exists()
