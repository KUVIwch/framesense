"""AI 分析器测试（云知声部分使用模拟 HTTP，不发起真实网络请求）。"""
from __future__ import annotations

import pytest
from PIL import Image

from framesense.ai.mock import MockAnalyzer
from framesense.ai.unisound import UnisoundAnalyzer
from framesense.models import AIAnalysis


def test_mock_analyzer_returns_deterministic(sample_image):
    analyzer = MockAnalyzer()
    img = Image.open(sample_image).convert("RGB")
    result = analyzer.analyze(img, "frame.png")
    assert isinstance(result, AIAnalysis)
    assert result.provider == "mock"
    assert "Mock" in result.summary
    assert result.keywords
    assert result.suggestions


def test_unisound_requires_config():
    with pytest.raises(ValueError):
        UnisoundAnalyzer(api_key="", api_base_url="https://example.com", model="m")
    with pytest.raises(ValueError):
        UnisoundAnalyzer(api_key="k", api_base_url="", model="m")
    with pytest.raises(ValueError):
        UnisoundAnalyzer(api_key="k", api_base_url="https://example.com", model="")


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def test_unisound_analyze_mock_http(sample_image, monkeypatch):
    captured = {}

    def fake_post(url, headers=None, json=None, timeout=None):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        return _FakeResponse({"choices": [{"message": {"content": "画面主体为移动小球|运动,动画|建议保留中间帧"}}]})

    monkeypatch.setattr("framesense.ai.unisound.requests.post", fake_post)

    analyzer = UnisoundAnalyzer(
        api_key="secret-key",
        api_base_url="https://api.example.com",
        model="vision-1",
    )
    img = Image.open(sample_image).convert("RGB")
    result = analyzer.analyze(img, "frame.png")

    assert result.provider == "unisound"
    assert "小球" in result.summary
    assert "运动" in result.keywords
    assert captured["url"] == "https://api.example.com/chat/completions"
    assert captured["headers"]["Authorization"] == "Bearer secret-key"
    assert "secret-key" not in str(captured["json"])
    assert captured["json"]["model"] == "vision-1"
    content = captured["json"]["messages"][0]["content"]
    image_url = content[1]["image_url"]["url"]
    assert image_url.startswith("data:image/jpeg;base64,")


def test_unisound_api_error_raises(sample_image, monkeypatch):
    class _FakeErrorResponse:
        def raise_for_status(self):
            raise RuntimeError("HTTP 500")

        def json(self):
            return {}

    def fake_post(*args, **kwargs):
        return _FakeErrorResponse()

    monkeypatch.setattr("framesense.ai.unisound.requests.post", fake_post)
    analyzer = UnisoundAnalyzer(
        api_key="k",
        api_base_url="https://api.example.com",
        model="m",
        max_retries=0,
    )
    img = Image.open(sample_image).convert("RGB")
    with pytest.raises(RuntimeError):
        analyzer.analyze(img, "frame.png")
