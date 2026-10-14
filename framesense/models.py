"""数据模型。"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class FrameFeatures:
    """单帧本地视觉特征。"""

    index: int
    filename: str
    path: str
    width: int
    height: int
    mode: str
    format: str
    file_size_bytes: int
    mean_brightness: float
    brightness_std: float
    mean_saturation: float
    unique_colors: int
    histogram: list[float]
    notes: list[str] = field(default_factory=list)


@dataclass
class FramePairDiff:
    """相邻帧差异。"""

    frame_a_index: int
    frame_b_index: int
    filename_a: str
    filename_b: str
    mae: float
    rmse: float
    histogram_distance: float
    diff_score: float
    is_keyframe_transition: bool = False
    note: str = ""


@dataclass
class AIAnalysis:
    """AI 语义分析结果。"""

    provider: str
    model: str
    summary: str
    keywords: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)
    raw: dict[str, Any] | None = None
    error: str | None = None


@dataclass
class FrameAnalysis:
    """单帧完整分析。"""

    index: int
    filename: str
    path: str
    features: FrameFeatures
    ai: AIAnalysis | None = None
    is_keyframe: bool = False
    keyframe_reason: str = ""


@dataclass
class SequenceReport:
    """序列分析报告。"""

    title: str
    generated_at: str
    source_path: str
    total_frames: int
    ai_mode: str
    ai_model: str
    threshold: float
    frames: list[FrameAnalysis] = field(default_factory=list)
    pair_diffs: list[FramePairDiff] = field(default_factory=list)
    keyframe_indices: list[int] = field(default_factory=list)
    overall_summary: str = ""
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """转为可 JSON 序列化的字典。"""
        return asdict(self)
