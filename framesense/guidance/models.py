"""调色指导的结构化模型（Pydantic 校验）。"""
from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class Observation(BaseModel):
    """一条观察：区分事实、推测与建议。"""

    kind: str = Field(description="fact / inference / suggestion")
    description: str

    @field_validator("kind")
    @classmethod
    def _check_kind(cls, value: str) -> str:
        if value not in {"fact", "inference", "suggestion"}:
            raise ValueError(f"未知观察类型: {value}")
        return value


class GuidanceStep(BaseModel):
    """一步可执行的调色指导。"""

    target: str
    observed_difference: str
    basis: str
    goal: str
    tool: str
    order: int = Field(ge=1)
    action: str
    expected_effect: str
    side_effects: str = ""
    observe_after: str = ""
    evidence_level: str = "suggestion"

    @field_validator("evidence_level")
    @classmethod
    def _check_evidence(cls, value: str) -> str:
        if value not in {"fact", "inference", "suggestion"}:
            raise ValueError(f"未知证据等级: {value}")
        return value


class GradingGuidance(BaseModel):
    """完整调色指导。"""

    summary: str
    observations: list[Observation] = Field(default_factory=list)
    steps: list[GuidanceStep] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    engine: str = "rule-v1"
    generated_at: str = ""
