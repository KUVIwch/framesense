"""命令行端到端测试。"""
from __future__ import annotations

from framesense.cli import main


def test_info_command(sample_image, capsys):
    rc = main(["info", str(sample_image)])
    assert rc == 0
    out = capsys.readouterr().out
    assert "尺寸" in out


def test_analyze_command(sample_frames, tmp_path, capsys):
    out_dir = tmp_path / "reports"
    rc = main(
        [
            "analyze",
            str(tmp_path),
            "--output-dir",
            str(out_dir),
            "--format",
            "both",
            "--ai-mode",
            "mock",
        ]
    )
    assert rc == 0
    files = list(out_dir.glob("framesense_report_*"))
    assert any(f.suffix == ".json" for f in files)
    assert any(f.suffix == ".md" for f in files)
    out = capsys.readouterr().out
    assert "分析完成" in out


def test_demo_command(tmp_path, capsys):
    out_dir = tmp_path / "demo"
    rc = main(["demo", "--output-dir", str(out_dir), "--frames", "3"])
    assert rc == 0
    assert len(list(out_dir.glob("frame_*.png"))) == 3
    report_files = list((out_dir / "report").glob("framesense_report_*"))
    assert len(report_files) == 2
    out = capsys.readouterr().out
    assert "分析完成" in out


def test_analyze_missing_path(capsys):
    rc = main(["analyze", "Z:/definitely_missing_dir"])
    assert rc != 0
