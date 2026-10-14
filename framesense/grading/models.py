"""调色方案结构化输出模型（Pydantic 校验）。"""
from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

VALID_PROVIDERS = {"mock", "openai", "unisound"}


class Adjustment(BaseModel):
    """单条调色建议。"""

    target: str = Field(min_length=1, description="调整项，如 曝光度/对比度/色温/高光/阴影")
    value: str = Field(min_length=1, description="建议值或操作（必须带单位），如 -0.3EV / +200K")
    rationale: str = Field(min_length=1, description="中文理由")
    priority: int = Field(default=2, ge=1, le=3, description="优先级 1-3，1 最重要")
    software: str = Field(default="", description="适用软件，如 Lightroom / Photoshop ACR / Capture One")
    note: str = Field(default="", description="必要说明，如适用条件、注意事项")


class ColorGradingPlan(BaseModel):
    """完整调色方案。"""

    summary: str = Field(min_length=1, description="整体方案摘要")
    global_adjustments: list[Adjustment] = Field(default_factory=list)
    color_adjustments: list[Adjustment] = Field(default_factory=list)
    local_adjustments: list[Adjustment] = Field(default_factory=list)
    artistic_features_to_preserve: list[str] = Field(default_factory=list)
    technical_issues: list[str] = Field(default_factory=list)
    intent_mapping: dict[str, str] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    model_provider: str = "mock"
    confidence: float = Field(default=0.5, ge=0, le=1)
    model_usage: dict | None = Field(default=None, description="模型 Token 用量（程序记录，不由模型填写）")
    model_duration_ms: int | None = Field(default=None, description="模型调用耗时毫秒（程序记录）")
    generation_status: str = Field(default="real", description="real=真实模型 / mock=规则方案 / repair=经一次修复")

    @field_validator("generation_status")
    @classmethod
    def _check_generation_status(cls, value: str) -> str:
        if value not in {"real", "mock", "repair"}:
            raise ValueError(f"未知生成状态: {value}")
        return value

    @field_validator("model_provider")
    @classmethod
    def _check_provider(cls, value: str) -> str:
        if value not in VALID_PROVIDERS:
            raise ValueError(f"未知模型提供方: {value}")
        return value


class IntentInput(BaseModel):
    """创作意图输入。"""

    keywords: list[str] = Field(min_length=1, max_length=3, description="情绪关键词 1-3 个")
    custom_note: str = Field(default="", max_length=500, description="补充说明")

    @field_validator("keywords")
    @classmethod
    def _clean_keywords(cls, value: list[str]) -> list[str]:
        cleaned = [k.strip() for k in value if k and k.strip()]
        if not cleaned:
            raise ValueError("至少需要一个情绪关键词")
        if len(cleaned) > 3:
            raise ValueError("最多 3 个情绪关键词")
        return cleaned
