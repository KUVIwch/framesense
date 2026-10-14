"""调色指导规则引擎。

输入：参考图（目标）统计、原片（源）统计、可选区域差异。
输出：可解释的分步指导。规则只使用已计算的客观指标，不编造精确数值；
涉及参数时给出方向与“起始范围”，并标记为 suggestion。
"""
from __future__ import annotations

from datetime import datetime, timezone

from framesense.guidance.models import GradingGuidance, GuidanceStep, Observation


def _fmt(value: float, digits: int = 1) -> str:
    return f"{value:.{digits}f}"


def generate_guidance(
    target_stats,
    source_stats,
    region_diffs: list[dict] | None = None,
) -> GradingGuidance:
    """生成仿色指导。target_stats=参考图，source_stats=原片。"""
    observations: list[Observation] = []
    steps: list[GuidanceStep] = []
    order = 1

    delta_brightness = target_stats.mean_brightness - source_stats.mean_brightness
    delta_std = target_stats.brightness_std - source_stats.brightness_std
    delta_b = target_stats.color_cast_lab["b"] - source_stats.color_cast_lab["b"]
    delta_a = target_stats.color_cast_lab["a"] - source_stats.color_cast_lab["a"]
    delta_chroma = target_stats.mean_chroma - source_stats.mean_chroma

    observations.append(
        Observation(
            kind="fact",
            description=(
                f"参考图平均亮度 {target_stats.mean_brightness:.0f}/255，"
                f"原片 {source_stats.mean_brightness:.0f}/255，差值为 {delta_brightness:+.1f}。"
            ),
        )
    )
    observations.append(
        Observation(
            kind="fact",
            description=(
                f"参考图平均色度 C* {target_stats.mean_chroma:.2f}，"
                f"原片 {source_stats.mean_chroma:.2f}，差值为 {delta_chroma:+.2f}。"
            ),
        )
    )

    # 1) 曝光/整体亮度
    if abs(delta_brightness) >= 8:
        direction = "提升" if delta_brightness > 0 else "降低"
        steps.append(
            GuidanceStep(
                target="曝光/整体亮度",
                observed_difference=f"参考图比原片整体亮度 {direction}约 {abs(delta_brightness):.0f}/255。",
                basis=f"mean_brightness 差值 {delta_brightness:+.1f}（阈值 ±8）",
                goal=f"让原片整体亮度向参考图靠拢（{direction}曝光）。",
                tool="Camera Raw：曝光",
                order=order,
                action=f"在 Camera Raw 中调整「曝光」滑块，向 {direction}方向从 0.3 EV 起步试调。",
                expected_effect="整体明暗关系向参考图接近。",
                side_effects="过度提升可能让高光溢出；过度降低可能让暗部死黑。",
                observe_after="观察直方图高光/暗部是否溢出，并与参考图亮度百分位对比。",
                evidence_level="suggestion",
            )
        )
        order += 1

    # 2) 对比度
    if abs(delta_std) >= 8:
        direction = "增强" if delta_std > 0 else "减弱"
        steps.append(
            GuidanceStep(
                target="对比度",
                observed_difference=f"参考图亮度标准差比原片 {direction}约 {abs(delta_std):.1f}。",
                basis=f"brightness_std 差值 {delta_std:+.1f}（阈值 ±8）",
                goal=f"{direction}对比度，使影调层次接近参考图。",
                tool="Camera Raw：对比度 / 曲线",
                order=order,
                action=f"先用「对比度」滑块向 {direction}方向调整；若仍不接近，再用 S 曲线微调。",
                expected_effect="影调压缩/拉伸方向与参考图一致。",
                side_effects="过度增强对比度会损失中间调细节或让颜色发硬。",
                observe_after="查看直方图两端是否出现明显的溢出。",
                evidence_level="suggestion",
            )
        )
        order += 1

    # 3) 色温
    if abs(delta_b) >= 2.0:
        direction = "偏暖" if delta_b > 0 else "偏冷"
        steps.append(
            GuidanceStep(
                target="色温",
                observed_difference=f"参考图整体色彩 b* 分量比原片 {direction}约 {abs(delta_b):.2f}。",
                basis=f"color_cast_lab.b 差值 {delta_b:+.2f}（阈值 ±2）",
                goal=f"让原片色温向参考图靠拢（{direction}）。",
                tool="Camera Raw：白平衡（色温）",
                order=order,
                action=f"调整「色温」滑块向 {direction}方向移动，从较小步长（约 200-400K）开始试。",
                expected_effect="整体色彩冷暖倾向接近参考图。",
                side_effects="过度调整会让皮肤或中性灰偏色。",
                observe_after="用白平衡吸管检查原本应为中性的区域是否还带色偏。",
                evidence_level="suggestion",
            )
        )
        order += 1

    # 4) 色调
    if abs(delta_a) >= 1.5:
        direction = "偏品红" if delta_a > 0 else "偏绿"
        steps.append(
            GuidanceStep(
                target="色调",
                observed_difference=f"参考图整体 a* 分量比原片 {direction}约 {abs(delta_a):.2f}。",
                basis=f"color_cast_lab.a 差值 {delta_a:+.2f}（阈值 ±1.5）",
                goal="让原片绿色/品红倾向与参考图一致。",
                tool="Camera Raw：白平衡（色调）",
                order=order,
                action=f"调整「色调」滑块向 {direction}方向微调。",
                expected_effect="肤色与中性色的品红/绿偏差更接近参考图。",
                side_effects="容易影响肤色，需在人物区域重点观察。",
                observe_after="观察肤色是否偏绿或偏品红。",
                evidence_level="suggestion",
            )
        )
        order += 1

    # 5) 饱和度/自然饱和度
    if abs(delta_chroma) >= 3.0:
        direction = "提升" if delta_chroma > 0 else "降低"
        steps.append(
            GuidanceStep(
                target="饱和度",
                observed_difference=f"参考图平均色度 C* 比原片 {direction}约 {abs(delta_chroma):.2f}。",
                basis=f"mean_chroma 差值 {delta_chroma:+.2f}（阈值 ±3）",
                goal=f"{direction}色彩浓郁程度，向参考图靠拢。",
                tool="Camera Raw：自然饱和度（优先）/ 饱和度",
                order=order,
                action=f"优先调整「自然饱和度」向 {direction}方向；若还不够再动「饱和度」。",
                expected_effect="色彩强度接近参考图，同时尽量保护肤色。",
                side_effects="自然饱和度过度提升会让低饱和区域发灰。",
                observe_after="观察最容易溢出的颜色（如红色通道）。",
                evidence_level="suggestion",
            )
        )
        order += 1

    # 6) 高光/暗部色偏
    for label, target_tint, source_tint, tool in (
        ("高光", target_stats.highlight_tint_lab, source_stats.highlight_tint_lab, "Camera Raw：高光/白色"),
        ("暗部", target_stats.shadow_tint_lab, source_stats.shadow_tint_lab, "Camera Raw：阴影/黑色"),
    ):
        da = target_tint["a"] - source_tint["a"]
        db = target_tint["b"] - source_tint["b"]
        if abs(da) >= 3.0 or abs(db) >= 3.0:
            steps.append(
                GuidanceStep(
                    target=f"{label}色偏",
                    observed_difference=f"{label}区域色相差异：a* {da:+.2f}，b* {db:+.2f}。",
                    basis=f"{label}_tint_lab 差值（阈值 ±3）",
                    goal=f"让{label}区域的颜色倾向更接近参考图。",
                    tool=tool,
                    order=order,
                    action=f"在 Camera Raw 的 HSL/颜色混合器中，针对{label}区域的颜色做局部偏移。",
                    expected_effect=f"{label}区域的色彩倾向更接近参考图。",
                    side_effects="可能影响相邻明暗区域的过渡。",
                    observe_after="观察高光到暗部的过渡是否自然。",
                    evidence_level="inference",
                )
            )
            order += 1

    # 7) 对应区域差异
    assumptions: list[str] = []
    if region_diffs:
        assumptions.append("区域差异基于用户手动选择的矩形区域计算。")
        for i, diff in enumerate(region_diffs, start=1):
            if diff.get("delta_e_cie2000", 0) >= 5:
                steps.append(
                    GuidanceStep(
                        target=f"对应区域 #{i}",
                        observed_difference=(
                            f"区域色差 ΔE00 = {diff.get('delta_e_cie2000', 0)}，"
                            f"亮度差 {diff.get('luma_delta', 0):+.2f}。"
                        ),
                        basis="region_difference CIE 2000（阈值 ΔE≥5）",
                        goal=f"让对应区域 #{i} 的颜色与明暗更接近参考区域。",
                        tool="Photoshop：调整图层 + 蒙版",
                        order=order,
                        action="创建曲线/色相饱和度调整图层，用蒙版只作用于该区域，按区域差异方向调整。",
                        expected_effect="对应区域的颜色差距缩小。",
                        side_effects="蒙版边缘可能出现生硬过渡，建议羽化。",
                        observe_after="放大检查区域边界是否自然。",
                        evidence_level="inference",
                    )
                )
                order += 1

    warnings = [
        "所有建议基于客观统计差异，不构成唯一正确的调色答案。",
        "涉及滑块数值均为方向性起始范围，请结合你的屏幕和意图微调。",
    ]
    if not steps:
        summary = "参考图与原片整体差异较小，可先以肉眼对照为主，不需要大幅调整。"
    else:
        summary = f"检测到 {len(steps)} 个可执行差异方向，按顺序从整体到局部调整。"

    return GradingGuidance(
        summary=summary,
        observations=observations,
        steps=steps,
        assumptions=assumptions,
        warnings=warnings,
        engine="rule-v1",
        generated_at=datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
    )
