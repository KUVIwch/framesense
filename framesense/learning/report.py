"""可带到 Camera Raw 旁边查看的本地练习记录。"""

from __future__ import annotations

from collections.abc import Mapping
import math
from numbers import Real


def _number(mapping, key):
    value = mapping.get(key) if isinstance(mapping, Mapping) else None
    if isinstance(value, Real) and not isinstance(value, bool) and math.isfinite(value):
        return float(value)
    return None


def _format(value, signed=False):
    return "—" if value is None else format(value, "+.3f" if signed else ".3f")


def _measurement_lines(analysis):
    """Export only known numeric fields, never photo paths or arbitrary payloads."""
    if not isinstance(analysis, Mapping):
        return []
    before, after = analysis.get("comparison"), analysis.get("final_comparison")
    lines = []
    if isinstance(before, Mapping) or isinstance(after, Mapping):
        lines += [
            "## 调整前后",
            "",
            "差值的方向为原片或成片减参考图；ΔE76 是平均 Lab 颜色之间的距离。",
            "",
            "| 测量 | 原片对参考 | 成片对参考 | 数值变化（成片 − 原片） |",
            "| --- | ---: | ---: | ---: |",
        ]
        for key, label, signed in (
            ("mean_luma_delta", "平均 L* 差值", True),
            ("mean_chroma_delta", "平均色度 C* 差值", True),
            ("mean_lab_delta_e", "平均颜色 ΔE76", False),
        ):
            initial, final = _number(before, key), _number(after, key)
            change = (
                final - initial if initial is not None and final is not None else None
            )
            lines.append(
                f"| {label} | {_format(initial, signed)} | {_format(final, signed)} | {_format(change, True)} |"
            )
        if not isinstance(after, Mapping):
            lines += ["", "尚未导入并分析成片，先保留原片的测量作为起点。"]
        lines += [
            "",
            "均值和采样分布会受场景、构图及物体占比影响；数值增减不等于调色进步或退步。",
            "",
        ]
    regions = analysis.get("region_diffs")
    if isinstance(regions, (list, tuple)) and any(
        isinstance(row, Mapping) for row in regions
    ):
        lines += [
            "## 对应区域",
            "",
            "以下为手动选择的原片区域对参考区域，差值方向为原片减参考图。",
            "",
            "| 区域 | 平均颜色 ΔE00 | L* 差值 | C* 差值 | a* 差值 | b* 差值 |",
            "| --- | ---: | ---: | ---: | ---: | ---: |",
        ]
        for index, row in enumerate(regions, 1):
            if not isinstance(row, Mapping):
                continue
            cells = [
                _format(_number(row, key), key != "delta_e_cie2000")
                for key in (
                    "delta_e_cie2000",
                    "luma_delta",
                    "chroma_delta",
                    "a_delta",
                    "b_delta",
                )
            ]
            lines.append(f"| {index} | " + " | ".join(cells) + " |")
        lines += [
            "",
            "ΔE00 只比较区域平均 Lab，可能掩盖内部纹理和混合颜色。请选可比材质与相近光照；极小区域受预览采样影响较大。",
            "",
        ]
    return lines


def practice_markdown(title, goal, guidance, notes="", analysis=None):
    lines = [
        f"# {title or '仿色练习'}",
        "",
        f"本次目标：{goal or '观察影调与颜色的关系。'}",
        "",
    ]
    lines += _measurement_lines(analysis)
    if guidance:
        lines += [guidance.summary, "", "## 观察", ""]
        for observation in guidance.observations:
            kind = {"fact": "测量", "inference": "推测", "suggestion": "建议"}[
                observation.kind
            ]
            lines.append(f"- {kind}：{observation.description}")
        for step in guidance.steps:
            lines += [
                "",
                f"## {step.order}. {step.target}",
                "",
                f"观察：{step.observed_difference}",
                f"依据：{step.basis}",
                f"工具：{step.tool}",
                f"试法：{step.action}",
                f"目的：{step.goal}",
                f"注意：{step.side_effects}",
                f"检查：{step.observe_after}",
            ]
        lines += ["", "## 使用边界", ""] + [
            f"- {s}" for s in guidance.assumptions + guidance.warnings
        ]
    if notes:
        lines += ["", "## 我的记录", "", notes]
    lines += [
        "",
        "这些测量描述照片的差异，不是对照片好坏的评分，也不能反推作者的原始参数。",
        "",
    ]
    return "\n".join(lines)
