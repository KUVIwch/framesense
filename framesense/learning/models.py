"""学习会话模型（Pydantic 校验）。"""
from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class RegionSpec(BaseModel):
    """矩形区域（绝对像素坐标）。"""

    x: int = Field(ge=0)
    y: int = Field(ge=0)
    width: int = Field(ge=1)
    height: int = Field(ge=1)


class LearningSession(BaseModel):
    """一个仿色练习项目。"""

    id: int | None = None
    title: str = ""
    created_at: str
    updated_at: str
    reference_path: str
    source_path: str
    final_path: str | None = None
    mode: str = "guided"
    notes: str = ""
    reference_region: RegionSpec | None = None
    source_region: RegionSpec | None = None
    guidance_json: dict = Field(default_factory=dict)
    analysis_json: dict = Field(default_factory=dict)

    @field_validator("mode")
    @classmethod
    def _check_mode(cls, value: str) -> str:
        if value not in {"guided", "practice", "independent"}:
            raise ValueError(f"未知学习模式: {value}")
        return value
