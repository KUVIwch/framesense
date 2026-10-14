"""调色决策流程测试。"""
from __future__ import annotations

import numpy as np
import pytest

from framesense.ai.vision import MockVisionClient
from framesense.analysis.exif import ExifData
from framesense.analysis.stats import compute_image_stats
from framesense.grading.decision import (
    _extract_json_object,
    build_analysis_payload,
    generate_suggestion,
)
from framesense.grading.models import ColorGradingPlan, IntentInput


def _make_stats(shadow_ratio=0.0, highlight_ratio=0.0, brightness_std=40.0):
    rgb = np.full((32, 32, 3), 120, dtype=np.uint8)
    flat = rgb.reshape(-1, 3)
    if shadow_ratio > 0:
        n = int(flat.shape[0] * shadow_ratio)
        flat[:n] = (8, 8, 8)
    if highlight_ratio > 0:
        n = int(flat.shape[0] * highlight_ratio)
        flat[-n:] = (248, 248, 248)
    rgb = flat.reshape(32, 32, 3)
    return compute_image_stats(rgb)


def test_generate_suggestion_without_client_returns_mock():
    stats = _make_stats()
    exif = ExifData(make="Sony", model="ILCE-7M4", iso=400, source="exifread")
    intent = IntentInput(keywords=["电影感", "暗调"])
    plan = generate_suggestion(stats=stats, exif=exif, intent=intent, client=None)
    assert isinstance(plan, ColorGradingPlan)
    assert plan.model_provider == "mock"
    assert plan.summary
    assert plan.intent_mapping
    assert plan.artistic_features_to_preserve
    assert 0 <= plan.confidence <= 1


def test_mock_dark_mood_does_not_brighten_shadows():
    stats = _make_stats(shadow_ratio=0.8, brightness_std=10.0)
    exif = ExifData()
    intent = IntentInput(keywords=["阴郁"])
    plan = generate_suggestion(stats=stats, exif=exif, intent=intent, client=None)
    shadow_adj = [a for a in plan.global_adjustments if a.target == "阴影"]
    assert shadow_adj
    assert "提亮" not in " ".join(a.value for a in shadow_adj)
    assert any("艺术表达" in a.rationale for a in shadow_adj)


def test_mock_bright_mood_with_dark_shadows_suggests_recovery():
    stats = _make_stats(shadow_ratio=0.8, brightness_std=10.0)
    exif = ExifData()
    intent = IntentInput(keywords=["明亮"])
    plan = generate_suggestion(stats=stats, exif=exif, intent=intent, client=None)
    shadow_adj = [a for a in plan.global_adjustments if a.target == "阴影"]
    assert shadow_adj
    assert any("提升" in a.value for a in shadow_adj)


def test_generate_suggestion_with_mock_client():
    stats = _make_stats()
    intent = IntentInput(keywords=["清新"])
    plan = generate_suggestion(stats=stats, exif=ExifData(), intent=intent, client=MockVisionClient())
    assert plan.model_provider == "mock"


def test_generate_suggestion_real_client_failure_does_not_fabricate():
    class FailingClient:
        def is_mock(self):
            return False

        def chat(self, payload, preview=None):
            raise RuntimeError("HTTP 500")

    stats = _make_stats()
    intent = IntentInput(keywords=["清新"])
    with pytest.raises(RuntimeError, match="未伪造分析结果"):
        generate_suggestion(stats=stats, exif=ExifData(), intent=intent, client=FailingClient())


def test_generate_suggestion_real_client_success(monkeypatch):
    class FakeClient:
        def is_mock(self):
            return False

        def chat(self, payload, preview=None):
            return '{"summary":"真实方案","model_provider":"openai","confidence":0.7,"global_adjustments":[]}'

    stats = _make_stats()
    intent = IntentInput(keywords=["温暖"])
    plan = generate_suggestion(stats=stats, exif=ExifData(), intent=intent, client=FakeClient())
    assert plan.model_provider == "openai"
    assert plan.summary == "真实方案"


def test_generate_suggestion_repair_after_invalid_json():
    """格式错误时执行一次修复，并标记 generation_status=repair。"""

    class RepairableClient:
        def is_mock(self):
            return False

        def __init__(self):
            self.calls = 0
            self.last_usage = {"total_tokens": 20}
            self.last_duration_ms = 42

        def chat(self, payload, preview=None):
            self.calls += 1
            return "这不是 JSON"

        def chat_with_meta(self, payload, preview=None, use_text_model=False):
            self.calls += 1
            return '{"summary":"修复后方案","model_provider":"openai","confidence":0.7}', {"total_tokens": 10}, 5

    plan = generate_suggestion(
        stats=_make_stats(),
        exif=ExifData(),
        intent=IntentInput(keywords=["清新"]),
        client=RepairableClient(),
    )
    assert plan.generation_status == "repair"
    assert plan.model_provider == "openai"
    assert plan.summary == "修复后方案"
    assert plan.model_usage == {"total_tokens": 20}
    assert plan.model_duration_ms == 42


def test_generate_suggestion_repair_failure_raises():
    """修复仍失败时必须明确报错，不得伪造分析结果。"""

    class BadClient:
        def is_mock(self):
            return False

        last_usage = None
        last_duration_ms = None

        def chat(self, payload, preview=None):
            return "这不是 JSON"

        def chat_with_meta(self, payload, preview=None, use_text_model=False):
            return "还是不是 JSON", None, 0

    with pytest.raises(RuntimeError, match="未伪造"):
        generate_suggestion(
            stats=_make_stats(),
            exif=ExifData(),
            intent=IntentInput(keywords=["清新"]),
            client=BadClient(),
        )


def test_build_analysis_payload_contains_all_sections():
    stats = _make_stats()
    exif = ExifData(make="Sony", iso=100, source="exifread")
    intent = IntentInput(keywords=["电影感"])
    payload = build_analysis_payload(stats, exif, intent, references=[_make_stats()])
    assert payload["exif"]["make"] == "Sony"
    assert payload["exif"]["iso"] == 100
    assert "image_stats" in payload
    assert payload["intent"]["keywords"] == ["电影感"]
    assert len(payload["reference_images"]) == 1


def test_extract_json_object_fences():
    data = _extract_json_object('```json\n{"summary":"x"}\n```')
    assert data == {"summary": "x"}


def test_extract_json_object_plain():
    data = _extract_json_object('{"summary":"y"}')
    assert data == {"summary": "y"}


def test_extract_json_object_invalid():
    with pytest.raises(ValueError):
        _extract_json_object("not json")
