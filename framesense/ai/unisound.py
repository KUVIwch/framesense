"""云知声视觉大模型适配器（可选）。

仅当用户显式指定 --ai-mode unisound 且配置了 UNISOUND_API_KEY 时才会发起网络请求。
默认 mock 模式不会调用任何远程 API。
"""
from __future__ import annotations

import base64
import io
import logging
import re

import requests
from PIL import Image

from framesense.ai.base import AIAnalyzer
from framesense.config import AppConfig
from framesense.models import AIAnalysis

logger = logging.getLogger(__name__)

DEFAULT_PROMPT = (
    "你是动画帧分析助手。请用简洁中文描述这张动画帧的内容："
    "画面主体、动作状态、光影、色彩；并给出 2-3 个关键词和 1 条制作建议。"
    "输出格式：摘要|关键词（逗号分隔）|建议。"
)


class UnisoundAnalyzer(AIAnalyzer):
    """云知声 OpenAI 兼容接口分析器。"""

    provider = "unisound"

    def __init__(
        self,
        api_key: str,
        api_base_url: str,
        model: str,
        timeout: float = 30.0,
        max_retries: int = 2,
    ):
        if not api_key:
            raise ValueError("缺少 UNISOUND_API_KEY，无法启用云知声模式")
        if not api_base_url:
            raise ValueError("缺少 UNISOUND_API_BASE_URL，无法启用云知声模式")
        if not model:
            raise ValueError("缺少 UNISOUND_MODEL，无法启用云知声模式")
        self.api_key = api_key
        self.api_base_url = api_base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.max_retries = max_retries

    @classmethod
    def from_config(cls, config: AppConfig) -> "UnisoundAnalyzer":
        """从应用配置构造分析器。"""
        return cls(
            api_key=config.unisound_api_key,
            api_base_url=config.unisound_api_base_url,
            model=config.unisound_model,
            timeout=config.request_timeout_seconds,
            max_retries=config.max_retries,
        )

    def _encode_image(self, image: Image.Image) -> str:
        """将图像编码为内存中的 JPEG base64 data URI，不写盘。"""
        buf = io.BytesIO()
        image.convert("RGB").save(buf, format="JPEG", quality=90)
        data = base64.b64encode(buf.getvalue()).decode("ascii")
        return f"data:image/jpeg;base64,{data}"

    def analyze(self, image: Image.Image, filename: str) -> AIAnalysis:
        """上传单帧到云知声并解析结果。调用方需已获得用户显式授权。"""
        url = f"{self.api_base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": DEFAULT_PROMPT},
                        {"type": "image_url", "image_url": {"url": self._encode_image(image)}},
                    ],
                }
            ],
            "temperature": 0.2,
        }

        last_exc: Exception | None = None
        for attempt in range(1, self.max_retries + 2):
            try:
                resp = requests.post(url, headers=headers, json=payload, timeout=self.timeout)
                resp.raise_for_status()
                data = resp.json()
                content = data["choices"][0]["message"]["content"]
                summary, keywords, suggestions = self._parse_content(content)
                return AIAnalysis(
                    provider=self.provider,
                    model=self.model,
                    summary=summary,
                    keywords=keywords,
                    suggestions=suggestions,
                    raw={"response": data} if isinstance(data, dict) else None,
                )
            except Exception as exc:
                last_exc = exc
                logger.warning("云知声 API 调用第 %d 次失败: %s", attempt, exc)
        raise RuntimeError(f"云知声 API 调用失败: {last_exc}") from last_exc

    @staticmethod
    def _parse_content(content: str) -> tuple[str, list[str], list[str]]:
        """解析 '摘要|关键词|建议' 格式的返回文本。"""
        text = str(content).strip()
        parts = [p.strip() for p in text.split("|")]
        summary = parts[0] if parts else text
        keywords: list[str] = []
        if len(parts) > 1:
            keywords = [k.strip() for k in re.split(r"[,，]", parts[1]) if k.strip()]
        suggestions: list[str] = []
        if len(parts) > 2 and parts[2].strip():
            suggestions = [parts[2].strip()]
        return summary, keywords, suggestions
