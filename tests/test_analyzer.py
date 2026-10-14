"""序列分析器测试。"""
from __future__ import annotations

import pytest

from framesense.ai.mock import MockAnalyzer
from framesense.analyzer import analyze_sequence
from framesense.features import sha256_of_file


def test_analyze_sequence_mock(sample_frames):
    report = analyze_sequence(
        sample_frames,
        ai_analyzer=MockAnalyzer(),
        threshold=0.2,
        ai_mode="mock",
    )
    assert report.total_frames == 6
    assert len(report.frames) == 6
    assert len(report.pair_diffs) == 5
    assert report.frames[0].is_keyframe is True
    assert report.keyframe_indices[0] == 0
    assert report.frames[0].ai is not None
    assert report.frames[0].ai.provider == "mock"


def test_analyze_sequence_empty_raises():
    with pytest.raises(ValueError):
        analyze_sequence([], ai_mode="mock")


def test_analyze_sequence_first_frame_always_keyframe(sample_frames):
    report = analyze_sequence(
        sample_frames,
        ai_analyzer=None,
        threshold=0.5,
        ai_mode="mock",
    )
    assert 0 in report.keyframe_indices


def test_analyze_sequence_invalid_threshold(sample_frames):
    with pytest.raises(ValueError):
        analyze_sequence(sample_frames, threshold=1.5, ai_mode="mock")


def test_original_files_unchanged(sample_frames):
    """分析前后原图哈希必须完全一致（只读保证）。"""
    before = {p: sha256_of_file(p) for p in sample_frames}
    analyze_sequence(
        sample_frames,
        ai_analyzer=MockAnalyzer(),
        threshold=0.2,
        ai_mode="mock",
    )
    after = {p: sha256_of_file(p) for p in sample_frames}
    assert before == after


def test_analysis_creates_no_files_near_input(sample_frames, tmp_path):
    """分析过程不得在输入目录旁产生任何新文件。"""
    analyze_sequence(
        sample_frames,
        ai_analyzer=MockAnalyzer(),
        threshold=0.2,
        ai_mode="mock",
    )
    assert sorted(p.name for p in tmp_path.iterdir()) == [
        f"frame_{i:03d}.png" for i in range(6)
    ]
