"""调色方案 Pydantic 模型测试。"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from framesense.grading.models import Adjustment, ColorGradingPlan, IntentInput


def test_valid_plan_parses():
    plan = ColorGradingPlan.model_validate(
        {
            "summary": "测试方案",
            "global_adjustments": [
                {"target": "曝光度", "value": "-0.3EV", "rationale": "保护高光", "priority": 1}
            ],
            "model_provider": "openai",
            "confidence": 0.8,
        }
    )
    assert plan.summary == "测试方案"
    assert plan.global_adjustments[0].target == "曝光度"
    assert plan.confidence == 0.8


def test_invalid_confidence_raises():
    with pytest.raises(ValidationError):
        ColorGradingPlan.model_validate({"summary": "x", "confidence": 1.5})


def test_invalid_provider_raises():
    with pytest.raises(ValidationError):
        ColorGradingPlan.model_validate({"summary": "x", "model_provider": "unknown"})


def test_adjustment_priority_bounds():
    with pytest.raises(ValidationError):
        Adjustment(target="曝光度", value="-1EV", rationale="x", priority=0)
    with pytest.raises(ValidationError):
        Adjustment(target="曝光度", value="-1EV", rationale="x", priority=4)


def test_intent_input_valid():
    intent = IntentInput(keywords=["电影感", "暗调"])
    assert intent.keywords == ["电影感", "暗调"]


def test_intent_input_empty_raises():
    with pytest.raises(ValidationError):
        IntentInput(keywords=[])


def test_intent_input_too_many_raises():
    with pytest.raises(ValidationError):
        IntentInput(keywords=["a", "b", "c", "d"])


def test_intent_input_cleans_whitespace():
    intent = IntentInput(keywords=["  电影感  ", "暗调"])
    assert intent.keywords == ["电影感", "暗调"]
