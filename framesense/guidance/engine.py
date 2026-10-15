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
    # Keep correction directions target-minus-source internally. Every displayed
    # signed measurement follows the workspace convention: source-minus-target.

    observations.append(
        Observation(
            kind="fact",
            description=(
                f"采样平均 Y′：原片 {source_stats.mean_brightness:.2f}/255，"
                f"参考 {target_stats.mean_brightness:.2f}/255；原片 − 参考 {-delta_brightness:+.1f}/255。"
                "Y′ 按编码 sRGB 的 Rec.709 权重统计，与比较面板的 Lab L*、曝光 EV 是不同量。"
            ),
        )
    )
    observations.append(
        Observation(
            kind="inference",
            description=(
                "全图均值会随场景、主体颜色和构图改变。先检查两张图是否有可比的主体或中性区域，"
                "再决定哪些差异值得模仿；软件不能仅凭 JPEG 推回作者的真实参数。"
            ),
        )
    )
    observations.append(
        Observation(
            kind="fact",
            description=(
                f"采样平均色度 C*：原片 {source_stats.mean_chroma:.2f}，"
                f"参考 {target_stats.mean_chroma:.2f}；原片 − 参考 {-delta_chroma:+.2f}。"
            ),
        )
    )

    # 1) 曝光/整体亮度
    if abs(delta_brightness) >= 8:
        direction = "提升" if delta_brightness > 0 else "降低"
        steps.append(
            GuidanceStep(
                target="曝光/整体亮度",
                observed_difference=f"平均 Y′ 差值（原片 − 参考）{-delta_brightness:+.1f}/255。",
                basis=f"采样 Y′ 均值差（原片 − 参考）{-delta_brightness:+.1f}/255；经验触发阈值 ±8，受物体占比影响。",
                goal=f"先比较主体与中间调；需要时{direction}曝光。",
                tool="Camera Raw：曝光",
                order=order,
                action=f"确认差异来自曝光而非场景后，试着向{direction}方向小幅移动「曝光」。可把 0.2 EV 作为试调起点，不是测量换算值。",
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
                observed_difference=f"Y′ 标准差之差（原片 − 参考）{-delta_std:+.1f}。",
                basis=f"采样 Y′ 标准差之差（原片 − 参考）{-delta_std:+.1f}；经验触发阈值 ±8，构图也会改变该值。",
                goal=f"{direction}对比度，使影调层次接近参考图。",
                tool="Camera Raw：对比度 / 曲线",
                order=order,
                action=f"先向{direction}对比度的方向小幅试调；必要时用曲线{'增大' if delta_std > 0 else '减小'}中段斜率，同时保留黑白端点细节。",
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
                observed_difference=f"全图平均 b* 差值（原片 − 参考）{-delta_b:+.2f}；b* 是黄蓝轴，不是白平衡测量。",
                basis=f"color_cast_lab.b 差值（原片 − 参考）{-delta_b:+.2f}；经验触发阈值 ±2，物体本身的颜色也会产生差异。",
                goal=f"在可比的中性区域确认是否需要{direction}，不要用全图 b* 判断白平衡是否错误。",
                tool="Camera Raw：白平衡（色温）",
                order=order,
                action=f"先对照相同材质或中性区域，确认后再把「色温」向{direction}方向小幅试调。JPEG 与 RAW 的滑块刻度不同，不给出固定 K 数换算。",
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
                observed_difference=f"全图平均 a* 差值（原片 − 参考）{-delta_a:+.2f}；a* 是红绿轴，不能单独确定白平衡色调。",
                basis=f"color_cast_lab.a 差值（原片 − 参考）{-delta_a:+.2f}；经验触发阈值 ±1.5，需先检查可比中性区域。",
                goal="让原片绿色/品红倾向与参考图一致。",
                tool="Camera Raw：白平衡（色调）",
                order=order,
                action=f"先确认中性区域也有同方向差异，再试着将「色调」向{direction}方向微调；不要把绿叶等物体颜色当成白平衡错误。",
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
                observed_difference=f"平均色度 C* 差值（原片 − 参考）{-delta_chroma:+.2f}。",
                basis=f"mean_chroma 差值（原片 − 参考）{-delta_chroma:+.2f}；经验触发阈值 ±3。",
                goal=f"{direction}色彩浓郁程度，向参考图靠拢。",
                tool="Camera Raw：自然饱和度（优先）/ 饱和度",
                order=order,
                action=f"优先调整「自然饱和度」向 {direction}方向；若还不够再动「饱和度」。",
                expected_effect="色彩强度接近参考图，同时尽量保护肤色。",
                side_effects="过度增加会让低饱和区域染色或使鲜艳颜色失去层次；降低过多则会发灰。",
                observe_after="观察最容易溢出的颜色（如红色通道）。",
                evidence_level="suggestion",
            )
        )
        order += 1

    # 6) 高光/暗部色偏
    for label, band, target_tint, source_tint in (
        (
            "高光",
            "highlight",
            target_stats.highlight_tint_lab,
            source_stats.highlight_tint_lab,
        ),
        (
            "中间调",
            "midtone",
            target_stats.midtone_tint_lab,
            source_stats.midtone_tint_lab,
        ),
        ("暗部", "shadow", target_stats.shadow_tint_lab, source_stats.shadow_tint_lab),
    ):
        # Absence of a tonal band is not a neutral tint measurement.
        if (
            min(
                target_stats.tonal_sample_counts.get(band, 0),
                source_stats.tonal_sample_counts.get(band, 0),
            )
            < 16
        ):
            continue
        da = target_tint["a"] - source_tint["a"]
        db = target_tint["b"] - source_tint["b"]
        if abs(da) >= 3.0 or abs(db) >= 3.0:
            steps.append(
                GuidanceStep(
                    target=f"{label}色偏",
                    observed_difference=f"{label}区域平均颜色差值（原片 − 参考）：a* {-da:+.2f}，b* {-db:+.2f}。",
                    basis=f"按 Y′ 明暗区间采样的平均 a*/b*，差值为原片 − 参考；经验触发阈值 ±3，两图该区间至少各 16 个样本。",
                    goal=f"让{label}区域的颜色倾向更接近参考图。",
                    tool=f"Camera Raw：颜色分级（{label}色轮）",
                    order=order,
                    action=f"先确认{label}中有可比材质，再试用「颜色分级」的{label}色轮；从低饱和度开始向所需颜色方向试调，并用混合/平衡检查过渡。若只影响一个物体，改用蒙版。",
                    expected_effect=f"{label}区域的色彩倾向更接近参考图。",
                    side_effects="可能影响相邻明暗区域的过渡。",
                    observe_after="观察高光到暗部的过渡是否自然。",
                    evidence_level="inference",
                )
            )
            order += 1

    # 7) 对应区域差异
    assumptions: list[str] = [
        "带正负号的差值统一为原片 − 参考；建议中的提升或降低则表示向参考靠拢的试调方向。",
        "测量来自转换到 sRGB 后的有限分辨率采样，明暗分区采用 Y′<64、64–192、>192；分区不是语义对象识别。",
        "先整理曝光与影调，再确认整体白平衡，最后考虑色彩浓度和局部；这只是经验顺序，可按创作意图调整。",
    ]
    if region_diffs:
        assumptions.append("区域差异基于用户手动选择的矩形区域计算。")
        for i, diff in enumerate(region_diffs, start=1):
            if diff.get("delta_e_cie2000", 0) >= 5:
                steps.append(
                    GuidanceStep(
                        target=f"对应区域 #{i}",
                        observed_difference=(
                            f"区域平均 Lab 色差 ΔE00 = {diff.get('delta_e_cie2000', 0)}，"
                            f"原片减参考图的 L* 差 {diff.get('luma_delta', 0):+.2f}、"
                            f"a* 差 {diff.get('a_delta', 0):+.2f}、b* 差 {diff.get('b_delta', 0):+.2f}。"
                        ),
                        basis="region_difference CIE 2000（阈值 ΔE≥5）",
                        goal=f"让对应区域 #{i} 的颜色与明暗更接近参考区域。",
                        tool="Camera Raw：蒙版 + 光线 / 颜色",
                        order=order,
                        action=f"在 Camera Raw 中建立对应区域的蒙版，先试着{'降低' if diff.get('luma_delta', 0) > 0 else '提高'}明暗，再按 a*/b* 差异小幅试调颜色；先确认两块区域是可比材质。",
                        expected_effect="对应区域的颜色差距缩小。",
                        side_effects="蒙版边缘可能出现生硬过渡，建议羽化。",
                        observe_after="放大检查区域边界是否自然。",
                        evidence_level="inference",
                    )
                )
                order += 1

    warnings = [
        "所有建议基于客观统计差异，不构成唯一正确的调色答案。",
        "触发阈值与滑块起点属于经验规则，没有从像素数值到 Camera Raw 参数的一一对应关系。",
        "均值相近可能掩盖不同颜色分布；场景不同、光照不同或物体占比不同，都可能产生与调色无关的差异。",
        "色彩管理统一为 sRGB；缺失或损坏 ICC 时按 sRGB 假设。显示器校准和超出 sRGB 的颜色不由此分析保证。",
    ]
    if not steps:
        summary = "这些全局统计差异较小，仍需对照主体和局部颜色；均值接近不能证明画面或风格相同。"
    else:
        summary = f"整理出 {len(steps)} 个可检查的差异方向。先确认场景可比，再选需要练习的步骤。"

    return GradingGuidance(
        summary=summary,
        observations=observations,
        steps=steps,
        assumptions=assumptions,
        warnings=warnings,
        engine="rule-v2",
        generated_at=datetime.now(timezone.utc)
        .astimezone()
        .isoformat(timespec="seconds"),
    )
