"""Portable practice exports: useful measurements with no image/session payload."""

from framesense.guidance.models import GradingGuidance, GuidanceStep, Observation
from framesense.learning.report import practice_markdown


def guidance():
    return GradingGuidance(
        summary="先看看主体亮度。",
        observations=[Observation(kind="fact", description="原片主体更暗。")],
        steps=[
            GuidanceStep(
                target="主体亮度",
                observed_difference="L* 较低",
                basis="区域采样",
                goal="保留主体细节",
                tool="Camera Raw：曝光",
                order=1,
                action="小幅试着提高曝光。",
                expected_effect="主体更亮",
                side_effects="高光可能溢出",
                observe_after="检查亮部细节",
            )
        ],
        assumptions=["两块区域为相近材质。"],
        warnings=["阈值属于经验规则。"],
    )


def test_guidance_and_notes_are_complete_without_analysis():
    result = practice_markdown("暖色练习", "观察主体", guidance(), "曝光先保持克制。")
    for expected in (
        "# 暖色练习",
        "本次目标：观察主体",
        "测量：原片主体更暗",
        "依据：区域采样",
        "工具：Camera Raw",
        "目的：保留主体细节",
        "检查：检查亮部细节",
        "高光可能溢出",
        "我的记录",
        "曝光先保持克制",
        "阈值属于经验规则",
    ):
        assert expected in result
    assert "不是对照片好坏的评分" in result


def test_before_after_metrics_have_explicit_direction_and_no_grade():
    analysis = {
        "comparison": {
            "mean_luma_delta": -10,
            "mean_chroma_delta": 4,
            "mean_lab_delta_e": 12,
        },
        "final_comparison": {
            "mean_luma_delta": -3,
            "mean_chroma_delta": 2,
            "mean_lab_delta_e": 7,
        },
    }
    result = practice_markdown("练习", "", None, analysis=analysis)
    assert "| 平均 L* 差值 | -10.000 | -3.000 | +7.000 |" in result
    assert "| 平均色度 C* 差值 | +4.000 | +2.000 | -2.000 |" in result
    assert "| 平均颜色 ΔE76 | 12.000 | 7.000 | -5.000 |" in result
    assert "数值增减不等于调色进步或退步" in result
    assert "场景" in result


def test_no_final_image_retains_initial_measurements():
    result = practice_markdown(
        "", "", None, analysis={"comparison": {"mean_luma_delta": 5}}
    )
    assert "# 仿色练习" in result
    assert "| 平均 L* 差值 | +5.000 | — | — |" in result
    assert "尚未导入并分析成片" in result


def test_region_report_includes_measured_values_and_limitations():
    result = practice_markdown(
        "",
        "",
        None,
        analysis={
            "region_diffs": [
                {
                    "delta_e_cie2000": 15.2,
                    "luma_delta": -4,
                    "chroma_delta": 6,
                    "a_delta": 2,
                    "b_delta": -3,
                }
            ]
        },
    )
    assert "| 1 | 15.200 | -4.000 | +6.000 | +2.000 | -3.000 |" in result
    assert "内部纹理和混合颜色" in result
    assert "可比材质" in result


def test_metadata_and_secret_like_payloads_are_never_serialized():
    payload = {
        "reference_path": "C:/private/photos/original.jpg",
        "source_path": "/private/photo.png",
        "api_key": "secret-that-must-stay-out",
        "photo": b"private-jpeg-binary",
        "comparison": {"mean_lab_delta_e": 5, "path": "sensitive-path"},
        "region_diffs": [
            {
                "delta_e_cie2000": 2,
                "photo": "base64-private-image",
                "note": "private-note",
            }
        ],
    }
    result = practice_markdown("", "", None, analysis=payload)
    for sensitive in (
        "C:/private",
        "/private",
        "secret-that-must-stay-out",
        "private-jpeg-binary",
        "sensitive-path",
        "base64-private-image",
        "private-note",
    ):
        assert sensitive not in result


def test_incomplete_old_and_nonfinite_payloads_do_not_break_export():
    for payload in (
        None,
        [],
        {},
        {"comparison": "old schema"},
        {
            "comparison": {
                "mean_luma_delta": float("nan"),
                "mean_chroma_delta": True,
                "mean_lab_delta_e": "not a number",
            },
            "final_comparison": {"mean_luma_delta": float("inf")},
            "region_diffs": [None, {"luma_delta": "bad"}],
        },
    ):
        result = practice_markdown("", "", None, analysis=payload)
        assert "不是对照片好坏的评分" in result
        assert "nan" not in result
        assert "inf" not in result
