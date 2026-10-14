"""序列分析编排。"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from framesense.ai.base import AIAnalyzer
from framesense.features import (
    brightness_std,
    compute_pair_diff,
    file_size_bytes,
    load_image,
    luminance_histogram,
    mean_brightness,
    mean_saturation,
    unique_colors,
)
from framesense.models import (
    AIAnalysis,
    FrameAnalysis,
    FrameFeatures,
    FramePairDiff,
    SequenceReport,
)

DEFAULT_THRESHOLD = 0.25


def _default_notes(features: FrameFeatures) -> list[str]:
    notes: list[str] = []
    if features.width < 64 or features.height < 64:
        notes.append("图像尺寸较小，AI 分析精度可能受限")
    if features.mean_brightness < 51:
        notes.append("图像整体偏暗")
    elif features.mean_brightness > 204:
        notes.append("图像整体偏亮")
    return notes


def analyze_sequence(
    paths: Iterable[str | Path],
    ai_analyzer: AIAnalyzer | None = None,
    threshold: float = DEFAULT_THRESHOLD,
    ai_mode: str = "mock",
    source_path: str | None = None,
) -> SequenceReport:
    """分析帧序列。

    Args:
        paths: 按播放顺序排列的图片路径。
        ai_analyzer: AI 分析器；为 None 时仅做本地分析。
        threshold: 关键帧切换阈值（0~1）。
        ai_mode: AI 模式名（仅用于报告）。
        source_path: 来源路径标签。
    """
    if not 0.0 <= threshold <= 1.0:
        raise ValueError(f"threshold 必须在 0~1 之间，当前: {threshold}")

    path_list = [Path(p).expanduser().resolve() for p in paths]
    if not path_list:
        raise ValueError("输入序列为空")

    if source_path is None:
        parents = {p.parent for p in path_list}
        source_path = str(path_list[0].parent if len(parents) > 1 else next(iter(parents)))

    frames: list[FrameAnalysis] = []
    pair_diffs: list[FramePairDiff] = []
    keyframe_indices: list[int] = []
    prev_img = None

    for i, p in enumerate(path_list):
        img = load_image(p)
        feats = FrameFeatures(
            index=i,
            filename=p.name,
            path=str(p),
            width=img.width,
            height=img.height,
            mode=img.mode,
            format=p.suffix.lstrip(".").upper() or "UNKNOWN",
            file_size_bytes=file_size_bytes(p),
            mean_brightness=mean_brightness(img),
            brightness_std=brightness_std(img),
            mean_saturation=mean_saturation(img),
            unique_colors=unique_colors(img),
            histogram=luminance_histogram(img),
            notes=[],
        )
        feats.notes = _default_notes(feats)

        ai: AIAnalysis | None = None
        if ai_analyzer is not None:
            try:
                ai = ai_analyzer.analyze(img, p.name)
            except Exception as exc:  # AI 失败不应阻断本地分析
                ai = AIAnalysis(
                    provider=getattr(ai_analyzer, "provider", "unknown"),
                    model=getattr(ai_analyzer, "model", "unknown"),
                    summary="",
                    keywords=[],
                    suggestions=[],
                    raw=None,
                    error=str(exc),
                )

        frame = FrameAnalysis(index=i, filename=p.name, path=str(p), features=feats, ai=ai)
        frames.append(frame)

        if prev_img is not None:
            diff = compute_pair_diff(prev_img, img)
            is_transition = diff["diff_score"] >= threshold
            pair = FramePairDiff(
                frame_a_index=i - 1,
                frame_b_index=i,
                filename_a=path_list[i - 1].name,
                filename_b=p.name,
                mae=diff["mae"],
                rmse=diff["rmse"],
                histogram_distance=diff["histogram_distance"],
                diff_score=diff["diff_score"],
                is_keyframe_transition=is_transition,
                note="关键帧切换" if is_transition else "过渡帧",
            )
            pair_diffs.append(pair)
            if is_transition:
                keyframe_indices.append(i)
                frame.is_keyframe = True
                frame.keyframe_reason = f"与上一帧差异 {diff['diff_score']:.3f} ≥ 阈值 {threshold}"
        prev_img = img

    # 第一帧始终作为关键帧
    if frames:
        frames[0].is_keyframe = True
        frames[0].keyframe_reason = "序列起始帧"
        if 0 not in keyframe_indices:
            keyframe_indices.insert(0, 0)

    notes: list[str] = []
    if ai_analyzer is None:
        notes.append("未启用 AI 分析（仅本地特征分析）")

    return SequenceReport(
        title="FrameSense 帧序列分析报告",
        generated_at=datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        source_path=source_path,
        total_frames=len(frames),
        ai_mode=ai_mode,
        ai_model=getattr(ai_analyzer, "model", "none") if ai_analyzer else "none",
        threshold=threshold,
        frames=frames,
        pair_diffs=pair_diffs,
        keyframe_indices=keyframe_indices,
        overall_summary=_build_summary(frames, pair_diffs, keyframe_indices),
        notes=notes,
    )


def _build_summary(
    frames: list[FrameAnalysis],
    pair_diffs: list[FramePairDiff],
    keyframe_indices: list[int],
) -> str:
    n = len(frames)
    if n == 0:
        return ""
    avg_brightness = sum(f.features.mean_brightness for f in frames) / n
    parts = [f"共 {n} 帧，识别出 {len(keyframe_indices)} 个关键帧（索引: {keyframe_indices or ['无']}）。"]
    parts.append(f"序列平均亮度约 {avg_brightness:.0f}/255。")
    if pair_diffs:
        max_diff = max(pair_diffs, key=lambda x: x.diff_score)
        parts.append(
            f"最大帧间差异出现在帧 {max_diff.frame_a_index}→{max_diff.frame_b_index}"
            f"（{max_diff.diff_score:.3f}）。"
        )
    return "".join(parts)
