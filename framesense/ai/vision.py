"""视觉模型客户端（OpenAI 兼容接口）。

支持任意 OpenAI 兼容的 chat/completions 端点：
- 官方 OpenAI
- 其他兼容服务（通过 OPENAI_BASE_URL 配置，如 vLLM、Ollama、通义等）

默认使用 mock 模式，不发起任何网络请求。上传预览图前必须先获得用户授权。
"""
from __future__ import annotations

import base64
import io
import json
import logging
import time
from typing import Any

import numpy as np
from PIL import Image
from openai import OpenAI

from framesense.ai.prompts import SYSTEM_PROMPT
from framesense.ai.errors import describe_error, is_retryable

logger = logging.getLogger(__name__)


class VisionModelClient:
    """OpenAI 兼容视觉模型客户端。"""

    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        timeout: float = 60.0,
        json_mode: bool = True,
        max_tokens: int = 4000,
        max_retries: int = 0,
        text_model: str = "",
        reasoning_effort: str = "",
    ):
        if not api_key:
            raise ValueError("缺少 OPENAI_API_KEY，无法启用 openai 视觉模式")
        if not base_url:
            raise ValueError("缺少 OPENAI_BASE_URL，无法启用 openai 视觉模式")
        if not model:
            raise ValueError("缺少 OPENAI_MODEL，无法启用 openai 视觉模式")
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.json_mode = json_mode
        self.max_tokens = max_tokens
        self.max_retries = max_retries
        self.text_model = text_model or model
        self.reasoning_effort = reasoning_effort
        self.last_usage: dict[str, Any] | None = None
        self.last_duration_ms: int | None = None

    def is_mock(self) -> bool:
        return False

    def chat(self, payload: dict[str, Any], preview: np.ndarray | None = None) -> str:
        """发送文本上下文（+可选预览图）到模型，返回模型文本内容。"""
        content, usage, duration_ms = self.chat_with_meta(payload, preview=preview)
        return content

    def chat_with_meta(
        self,
        payload: dict[str, Any],
        preview: np.ndarray | None = None,
        use_text_model: bool = False,
    ) -> tuple[str, dict[str, Any] | None, int]:
        """发送请求并返回 (内容, token 用量, 耗时毫秒)。"""
        client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=self.timeout,
            max_retries=0,
        )
        user_content: list[dict[str, Any]] = [
            {"type": "text", "text": json.dumps(payload, ensure_ascii=False, default=str)}
        ]
        if preview is not None:
            user_content.append({"type": "image_url", "image_url": {"url": encode_preview(preview)}})

        kwargs: dict[str, Any] = {
            "model": self.text_model if use_text_model else self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            "temperature": 0.3,
        }
        if self.json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        if self.max_tokens > 0:
            kwargs["max_tokens"] = self.max_tokens
        if self.reasoning_effort:
            kwargs["reasoning_effort"] = self.reasoning_effort

        last_exc: Exception | None = None
        start = time.monotonic()
        for attempt in range(1, self.max_retries + 2):
            try:
                resp = client.chat.completions.create(**kwargs)
                self.last_duration_ms = int((time.monotonic() - start) * 1000)
                usage: dict[str, Any] | None = None
                usage_obj = getattr(resp, "usage", None)
                if usage_obj is not None:
                    usage = {
                        "prompt_tokens": int(getattr(usage_obj, "prompt_tokens", 0) or 0),
                        "completion_tokens": int(getattr(usage_obj, "completion_tokens", 0) or 0),
                        "total_tokens": int(getattr(usage_obj, "total_tokens", 0) or 0),
                    }
                self.last_usage = usage
                return resp.choices[0].message.content or "", usage, self.last_duration_ms
            except Exception as exc:
                last_exc = exc
                if attempt <= self.max_retries and is_retryable(exc):
                    time.sleep(min(2**attempt, 8))
                else:
                    break
        raise RuntimeError(f"视觉模型 API 调用失败：{describe_error(last_exc)}") from last_exc


class MockVisionClient(VisionModelClient):
    """Mock 客户端：不发起任何网络请求。"""

    def __init__(self):
        self.api_key = ""
        self.base_url = ""
        self.model = "mock-v0.2"
        self.timeout = 0.0
        self.json_mode = True

    def is_mock(self) -> bool:
        return True

    def chat(self, payload: dict[str, Any], preview: np.ndarray | None = None) -> str:
        raise RuntimeError("Mock 客户端不应直接调用 chat()；请使用 generate_suggestion 的 mock 分支")


def encode_preview(preview: np.ndarray, max_side: int = 1024) -> str:
    """将预览图编码为 JPEG base64 data URI（仅内存，不落盘）。"""
    from framesense.analysis.loader import make_preview

    pv = make_preview(preview, max_side=max_side)
    buf = io.BytesIO()
    Image.fromarray(pv).save(buf, format="JPEG", quality=85)
    data = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/jpeg;base64,{data}"


def create_vision_client(config, custom: dict | None = None) -> VisionModelClient:
    """按配置创建视觉模型客户端。

    Args:
        config: AppConfig 实例。
        custom: 可选的用户自定义配置 dict，包含 api_key/base_url/model。
            三个字段都非空时优先使用；Key 仅用于本次会话，不落盘。

    - custom 有效：创建使用自定义端点的真实客户端。
    - 否则若 vision_mode=openai：创建真实客户端（缺少 Key 时抛出 ValueError）。
    - 否则（默认）：返回 Mock 客户端，零网络调用。
    """
    custom = custom or {}
    if custom.get("api_key") and custom.get("base_url") and custom.get("model"):
        return VisionModelClient(
            api_key=custom["api_key"].strip(),
            base_url=custom["base_url"].strip(),
            model=custom["model"].strip(),
            timeout=config.request_timeout_seconds,
            json_mode=config.openai_json_mode,
            max_tokens=config.openai_max_tokens,
            max_retries=config.max_retries,
            text_model=config.openai_text_model,
            reasoning_effort=config.reasoning_effort,
        )
    if config.vision_mode == "openai":
        return VisionModelClient(
            api_key=config.openai_api_key,
            base_url=config.openai_base_url,
            model=config.openai_model,
            timeout=config.request_timeout_seconds,
            json_mode=config.openai_json_mode,
            max_tokens=config.openai_max_tokens,
            max_retries=config.max_retries,
            text_model=config.openai_text_model,
            reasoning_effort=config.reasoning_effort,
        )
    return MockVisionClient()
