"""Mock AI 分析器：纯本地规则，无网络调用、无 API 费用。"""
from __future__ import annotations

from PIL import Image

from framesense.ai.base import AIAnalyzer
from framesense.features import mean_brightness, mean_saturation
from framesense.models import AIAnalysis


class MockAnalyzer(AIAnalyzer):
    """基于亮度与饱和度的确定性模拟分析。"""

    provider = "mock"
    model = "mock-v0.1"

    def analyze(self, image: Image.Image, filename: str) -> AIAnalysis:
        brightness = mean_brightness(image)
        saturation = mean_saturation(image)
        width, height = image.size

        if brightness < 76:
            light_desc = "偏暗"
            suggestion = "可考虑提升亮度，便于后续关键帧识别"
        elif brightness > 179:
            light_desc = "偏亮"
            suggestion = "可检查是否过曝，必要时调整曝光"
        else:
            light_desc = "适中"
            suggestion = "亮度正常，无需调整"

        if saturation < 0.15:
            color_desc = "色彩饱和度低"
            keyword = "低饱和"
        elif saturation > 0.5:
            color_desc = "色彩饱和度高"
            keyword = "高饱和"
        else:
            color_desc = "色彩饱和度适中"
            keyword = "中等饱和"

        summary = (
            f"【Mock 分析】帧 {filename}：{width}x{height}，"
            f"整体亮度{light_desc}（{brightness:.0f}/255），{color_desc}。"
        )
        return AIAnalysis(
            provider=self.provider,
            model=self.model,
            summary=summary,
            keywords=[light_desc, keyword],
            suggestions=[suggestion],
            raw={"mock": True, "brightness": round(brightness, 1), "saturation": round(saturation, 3)},
        )
