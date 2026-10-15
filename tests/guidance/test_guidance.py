"""调色指导引擎测试。"""

from __future__ import annotations

import numpy as np
import pytest
from PIL import Image
from pydantic import ValidationError

from framesense.core.stats import compute_image_stats
from framesense.guidance.engine import generate_guidance
from framesense.guidance.models import GuidanceStep


def _rgb(size, color):
    return np.asarray(Image.new("RGB", size, color), dtype=np.uint8)


def _make_image(bright: bool, warm: bool, saturated: bool) -> np.ndarray:
    img = np.zeros((64, 64, 3), dtype=np.uint8)
    base = 180 if bright else 60
    img[:, :] = (base, base, base)
    if warm:
        img[:, :, 0] = np.clip(img[:, :, 0] + 30, 0, 255)
        img[:, :, 2] = np.clip(img[:, :, 2] - 30, 0, 255)
    if saturated:
        img[16:48, 16:48] = (230, 80, 60) if warm else (60, 120, 220)
    return img


def test_guidance_detects_brightness_warmth_saturation():
    source = compute_image_stats(_make_image(bright=False, warm=False, saturated=False))
    target = compute_image_stats(_make_image(bright=True, warm=True, saturated=True))
    guidance = generate_guidance(target_stats=target, source_stats=source)
    assert guidance.steps
    targets = {step.target for step in guidance.steps}
    assert "曝光/整体亮度" in targets
    assert "色温" in targets
    assert "饱和度" in targets
    assert any(o.kind == "fact" for o in guidance.observations)
    assert all(
        step.evidence_level in {"fact", "inference", "suggestion"}
        for step in guidance.steps
    )


def test_guidance_identical_images_minimal_steps():
    img = _make_image(bright=True, warm=True, saturated=True)
    stats = compute_image_stats(img)
    guidance = generate_guidance(target_stats=stats, source_stats=stats)
    assert not guidance.steps
    assert "差异较小" in guidance.summary


def test_guidance_region_diffs_add_local_steps():
    source = compute_image_stats(_make_image(bright=False, warm=False, saturated=False))
    target = compute_image_stats(_make_image(bright=True, warm=True, saturated=True))
    region_diffs = [
        {
            "delta_e_cie2000": 18.5,
            "luma_delta": 20.0,
            "chroma_delta": 5.0,
            "a_delta": 10,
            "b_delta": 8,
        }
    ]
    guidance = generate_guidance(
        target_stats=target, source_stats=source, region_diffs=region_diffs
    )
    assert any("对应区域" in step.target for step in guidance.steps)
    assert guidance.assumptions


def test_guidance_does_not_fabricate_precise_values():
    source = compute_image_stats(_make_image(bright=False, warm=False, saturated=False))
    target = compute_image_stats(_make_image(bright=True, warm=True, saturated=True))
    guidance = generate_guidance(target_stats=target, source_stats=source)
    for step in guidance.steps:
        assert "起始" in step.action or "方向" in step.action or "试" in step.action
        assert step.evidence_level in {"inference", "suggestion"}


def test_guidance_step_validation():
    with pytest.raises(ValidationError):
        GuidanceStep(
            target="x",
            observed_difference="x",
            basis="x",
            goal="x",
            tool="x",
            order=1,
            action="x",
            evidence_level="invalid",
        )


def test_tonal_color_uses_grading_wheels_and_skips_absent_bands():
    target = compute_image_stats(_rgb((32, 32), (150, 120, 100)))
    source = compute_image_stats(_rgb((32, 32), (100, 120, 150)))
    guidance = generate_guidance(target, source)
    tonal = [step for step in guidance.steps if "色偏" in step.target]
    assert tonal
    assert all("颜色分级" in step.tool for step in tonal)
    assert all("中间调" in step.target for step in tonal)


def test_guidance_explains_scene_and_parameter_uncertainty():
    stats = compute_image_stats(_rgb((32, 32), (120, 120, 120)))
    guidance = generate_guidance(stats, stats)
    text = " ".join(
        guidance.warnings
        + guidance.assumptions
        + [o.description for o in guidance.observations]
    )
    assert "场景" in text
    assert "JPEG" in text
    assert "经验" in text


def test_displayed_deltas_follow_source_minus_reference_and_actions_still_correct():
    from dataclasses import replace

    base = compute_image_stats(_rgb((32, 32), (120, 120, 120)))
    source = replace(
        base,
        mean_brightness=60,
        brightness_std=10,
        mean_chroma=20,
        color_cast_lab={"a": 5, "b": 8},
        midtone_tint_lab={"a": 5, "b": 8},
    )
    target = replace(
        base,
        mean_brightness=180,
        brightness_std=30,
        mean_chroma=10,
        color_cast_lab={"a": 0, "b": 0},
        midtone_tint_lab={"a": 0, "b": 0},
    )
    guidance = generate_guidance(target, source)
    facts = [
        observation.description
        for observation in guidance.observations
        if observation.kind == "fact"
    ]
    assert "原片 − 参考 -120.0/255" in facts[0]
    assert "原片 − 参考 +10.00" in facts[1]
    assert "Lab L*" in facts[0]
    assert "曝光 EV" in facts[0]
    steps = {step.target: step for step in guidance.steps}
    expected = {
        "曝光/整体亮度": "-120.0",
        "对比度": "-20.0",
        "色温": "+8.00",
        "色调": "+5.00",
        "饱和度": "+10.00",
    }
    for target_name, delta in expected.items():
        step = steps[target_name]
        assert "原片 − 参考" in step.observed_difference
        assert delta in step.observed_difference
        assert delta in step.basis
    assert "提升" in steps["曝光/整体亮度"].action
    assert "增强" in steps["对比度"].action
    assert "降低" in steps["饱和度"].action
    assert "偏冷" in steps["色温"].action
    assert "偏绿" in steps["色调"].action
    assert "a* +5.00，b* +8.00" in steps["中间调色偏"].observed_difference


def test_color_axis_measurements_are_not_claimed_as_white_balance_facts():
    source = compute_image_stats(_rgb((32, 32), (150, 120, 100)))
    reference = compute_image_stats(_rgb((32, 32), (100, 120, 150)))
    steps = {step.target: step for step in generate_guidance(reference, source).steps}
    assert "不是白平衡测量" in steps["色温"].observed_difference
    assert "不能单独确定白平衡" in steps["色调"].observed_difference
    assert steps["色温"].evidence_level == "suggestion"
