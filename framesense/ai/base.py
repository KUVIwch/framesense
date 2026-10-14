"""AI 分析抽象接口与工厂。"""
from __future__ import annotations

from abc import ABC, abstractmethod

from PIL import Image

from framesense.models import AIAnalysis


class AIAnalyzer(ABC):
    """AI 分析器抽象基类。"""

    provider: str = "base"
    model: str = ""

    @abstractmethod
    def analyze(self, image: Image.Image, filename: str) -> AIAnalysis:
        """分析单帧图像，返回语义分析结果。"""
        raise NotImplementedError


def create_analyzer(mode: str, config) -> AIAnalyzer:
    """按模式创建分析器。

    Args:
        mode: mock 或 unisound。
        config: AppConfig 实例。
    """
    from framesense.ai.mock import MockAnalyzer
    from framesense.ai.unisound import UnisoundAnalyzer

    if mode == "mock":
        return MockAnalyzer()
    if mode == "unisound":
        return UnisoundAnalyzer.from_config(config)
    raise ValueError(f"未知 AI 模式: {mode}")
