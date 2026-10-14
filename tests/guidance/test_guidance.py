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
    assert all(step.evidence_level in {"fact", "inference", "suggestion"} for step in guidance.steps)


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
        {"delta_e_cie2000": 18.5, "luma_delta": 20.0, "chroma_delta": 5.0, "a_delta": 10, "b_delta": 8}
    ]
    guidance = generate_guidance(target_stats=target, source_stats=source, region_diffs=region_diffs)
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
