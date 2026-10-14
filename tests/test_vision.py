"""视觉模型客户端测试（模拟 OpenAI SDK，不发起真实网络请求）。"""
from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

from framesense.ai.vision import (
    MockVisionClient,
    VisionModelClient,
    create_vision_client,
    encode_preview,
)
from framesense.config import load_config


def test_mock_client_never_network():
    client = MockVisionClient()
    assert client.is_mock() is True
    with pytest.raises(RuntimeError):
        client.chat({"x": 1})


def test_vision_client_requires_config():
    with pytest.raises(ValueError):
        VisionModelClient(api_key="", base_url="https://api.example.com", model="m")
    with pytest.raises(ValueError):
        VisionModelClient(api_key="k", base_url="", model="m")
    with pytest.raises(ValueError):
        VisionModelClient(api_key="k", base_url="https://api.example.com", model="")


def test_vision_chat_success(monkeypatch):
    captured = {}

    class FakeCompletions:
        def create(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content='{"summary":"ok"}'))]
            )

    class FakeChat:
        completions = FakeCompletions()

    class FakeOpenAI:
        def __init__(self, api_key, base_url, timeout, **kwargs):
            captured["client_args"] = (api_key, base_url, timeout)
            self.chat = FakeChat()

    monkeypatch.setattr("framesense.ai.vision.OpenAI", FakeOpenAI)
    client = VisionModelClient("secret", "https://api.example.com/v1", "vision-1", timeout=10)
    content = client.chat({"intent": "电影感"}, preview=None)
    assert content == '{"summary":"ok"}'
    assert captured["client_args"] == ("secret", "https://api.example.com/v1", 10)
    assert captured["model"] == "vision-1"
    assert captured["response_format"] == {"type": "json_object"}
    messages = captured["messages"]
    assert messages[0]["role"] == "system"
    assert "资深摄影后期调色师" in messages[0]["content"]
    assert messages[1]["role"] == "user"


def test_vision_chat_with_preview(monkeypatch):
    captured = {}

    class FakeCompletions:
        def create(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content='{"summary":"ok"}'))]
            )

    class FakeChat:
        completions = FakeCompletions()

    class FakeOpenAI:
        def __init__(self, api_key, base_url, timeout, **kwargs):
            self.chat = FakeChat()

    monkeypatch.setattr("framesense.ai.vision.OpenAI", FakeOpenAI)
    client = VisionModelClient("secret", "https://api.example.com/v1", "vision-1")
    preview = np.zeros((100, 100, 3), dtype=np.uint8)
    content = client.chat({"intent": "清新"}, preview=preview)
    assert content == '{"summary":"ok"}'
    user_content = captured["messages"][1]["content"]
    assert len(user_content) == 2
    assert user_content[1]["type"] == "image_url"
    assert user_content[1]["image_url"]["url"].startswith("data:image/jpeg;base64,")


def test_vision_chat_failure_raises(monkeypatch):
    class FailingCompletions:
        def create(self, **kwargs):
            raise RuntimeError("HTTP 503")

    class FakeChat:
        completions = FailingCompletions()

    class FakeOpenAI:
        def __init__(self, api_key, base_url, timeout, **kwargs):
            self.chat = FakeChat()

    monkeypatch.setattr("framesense.ai.vision.OpenAI", FakeOpenAI)
    client = VisionModelClient("secret", "https://api.example.com/v1", "vision-1")
    with pytest.raises(RuntimeError, match="视觉模型 API 调用失败"):
        client.chat({"x": 1})


def test_encode_preview_data_uri():
    preview = np.zeros((64, 64, 3), dtype=np.uint8)
    uri = encode_preview(preview)
    assert uri.startswith("data:image/jpeg;base64,")


def test_create_vision_client_mock(monkeypatch, tmp_path):
    monkeypatch.delenv("FRAMESENSE_VISION_MODE", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    monkeypatch.delenv("FRAMESENSE_REQUEST_TIMEOUT", raising=False)
    monkeypatch.delenv("FRAMESENSE_MAX_RETRIES", raising=False)
    monkeypatch.delenv("FRAMESENSE_JSON_MODE", raising=False)
    monkeypatch.delenv("FRAMESENSE_MAX_TOKENS", raising=False)
    empty_env = tmp_path / "nonexistent.env"
    config = load_config(env_path=empty_env, ai_mode="mock")
    client = create_vision_client(config)
    assert isinstance(client, MockVisionClient)


def test_create_vision_client_openai(monkeypatch):
    monkeypatch.setenv("FRAMESENSE_VISION_MODE", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "k")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://api.example.com/v1")
    monkeypatch.setenv("OPENAI_MODEL", "vision-1")
    config = load_config(ai_mode="mock")
    client = create_vision_client(config)
    assert isinstance(client, VisionModelClient)
    assert client.model == "vision-1"


def test_create_vision_client_custom(monkeypatch, tmp_path):
    monkeypatch.delenv("FRAMESENSE_VISION_MODE", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    monkeypatch.delenv("FRAMESENSE_REQUEST_TIMEOUT", raising=False)
    monkeypatch.delenv("FRAMESENSE_MAX_RETRIES", raising=False)
    monkeypatch.delenv("FRAMESENSE_JSON_MODE", raising=False)
    monkeypatch.delenv("FRAMESENSE_MAX_TOKENS", raising=False)
    config = load_config(env_path=tmp_path / "nonexistent.env", ai_mode="mock")
    client = create_vision_client(
        config,
        custom={"api_key": "my-key", "base_url": "https://my-api.example.com/v1", "model": "my-vision"},
    )
    assert isinstance(client, VisionModelClient)
    assert client.model == "my-vision"
    assert client.base_url == "https://my-api.example.com/v1"


def test_create_vision_client_custom_incomplete_falls_back(monkeypatch, tmp_path):
    monkeypatch.delenv("FRAMESENSE_VISION_MODE", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    monkeypatch.delenv("FRAMESENSE_REQUEST_TIMEOUT", raising=False)
    monkeypatch.delenv("FRAMESENSE_MAX_RETRIES", raising=False)
    monkeypatch.delenv("FRAMESENSE_JSON_MODE", raising=False)
    monkeypatch.delenv("FRAMESENSE_MAX_TOKENS", raising=False)
    config = load_config(env_path=tmp_path / "nonexistent.env", ai_mode="mock")
    client = create_vision_client(config, custom={"api_key": "my-key", "base_url": "", "model": ""})
    assert isinstance(client, MockVisionClient)
