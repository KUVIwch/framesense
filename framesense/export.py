"""Markdown 报告导出。"""
from __future__ import annotations

from pathlib import Path

from framesense.grading.models import ColorGradingPlan, IntentInput


def build_markdown_report(
    filename: str,
    exif,
    stats,
    intent: IntentInput,
    plan: ColorGradingPlan,
    references=None,
) -> str:
    """生成中文 Markdown 报告。"""
    refs = references or []
    lines: list[str] = []
    lines.append("# FrameSense 摄影分析与调色建议报告")
    lines.append("")
    lines.append(f"- 源文件：`{filename}`")
    lines.append(f"- 尺寸：{stats.width} x {stats.height}")
    lines.append(f"- 情绪关键词：{'、'.join(intent.keywords)}")
    if intent.custom_note:
        lines.append(f"- 补充说明：{intent.custom_note}")
    lines.append(f"- 模型提供方：{plan.model_provider}（置信度 {plan.confidence:.2f}）")
    lines.append(f"- 生成状态：{plan.generation_status}（real=真实模型 / mock=规则方案 / repair=经一次修复）")
    if plan.model_duration_ms is not None:
        lines.append(f"- 模型耗时：{plan.model_duration_ms} ms")
    if plan.model_usage:
        lines.append(f"- Token 用量：{plan.model_usage}")
    if plan.model_provider == "mock":
        lines.append("- 提示：本报告为 **Mock 规则方案**，未调用真实视觉模型。")
    lines.append("")

    lines.append("## 一、可用 EXIF 数据")
    lines.append("")
    if exif is None:
        lines.append("（无可用 EXIF 数据）")
    else:
        mapping = [
            ("相机厂商", exif.make),
            ("相机型号", exif.model),
            ("镜头", exif.lens_model),
            ("ISO", exif.iso),
            ("快门速度", exif.shutter_speed),
            ("光圈", exif.aperture),
            ("焦距", exif.focal_length),
            ("曝光补偿", exif.exposure_bias),
            ("白平衡", exif.white_balance),
            ("拍摄时间", exif.taken_at),
        ]
        available = [(label, value) for label, value in mapping if value is not None]
        if available:
            for label, value in available:
                lines.append(f"- {label}：{value}")
        else:
            lines.append("（文件中未读取到 EXIF 拍摄参数，以下不包含任何 EXIF 推断）")
    lines.append("")

    lines.append("## 二、客观图像统计")
    lines.append("")
    lines.append(f"- 平均亮度：{stats.mean_brightness:.1f}/255")
    lines.append(f"- 亮度标准差：{stats.brightness_std:.1f}")
    lines.append(f"- 暗部占比（<64/255）：{stats.shadow_ratio * 100:.1f}%")
    lines.append(f"- 中间调占比：{stats.midtone_ratio * 100:.1f}%")
    lines.append(f"- 亮部占比（>192/255）：{stats.highlight_ratio * 100:.1f}%")
    lines.append(f"- 平均饱和度：{stats.mean_saturation:.3f}")
    lines.append(f"- 清晰度代理（边缘能量）：{stats.edge_density:.2f}")
    lines.append(f"- 主色：{', '.join(c['hex'] for c in stats.dominant_colors[:3])}")
    lines.append(f"- 色偏估计（灰世界）：{stats.color_cast}")
    lines.append("")

    if refs:
        lines.append("## 三、参考作品统计")
        lines.append("")
        for i, ref_stats in enumerate(refs, start=1):
            lines.append(
                f"- 参考 {i}：{ref_stats.width}x{ref_stats.height}，"
                f"平均亮度 {ref_stats.mean_brightness:.0f}，主色 {', '.join(c['hex'] for c in ref_stats.dominant_colors[:3])}"
            )
        lines.append("")
        next_section = "四"
    else:
        next_section = "三"

    lines.append(f"## {next_section}、调色方案")
    lines.append("")
    lines.append(plan.summary)
    lines.append("")

    lines.append(f"### {next_section}.1 全局调整")
    lines.append("")
    for adj in plan.global_adjustments or []:
        lines.append(f"- **{adj.target}**：{adj.value}（优先级 {adj.priority}）")
        lines.append(f"  - 理由：{adj.rationale}")
        if adj.software or adj.note:
            lines.append(f"  - 适用软件：{adj.software or '未指定'}；说明：{adj.note or '无'}")
    if not plan.global_adjustments:
        lines.append("- 无")
    lines.append("")

    lines.append(f"### {next_section}.2 色彩调整")
    lines.append("")
    for adj in plan.color_adjustments or []:
        lines.append(f"- **{adj.target}**：{adj.value}（优先级 {adj.priority}）")
        lines.append(f"  - 理由：{adj.rationale}")
        if adj.software or adj.note:
            lines.append(f"  - 适用软件：{adj.software or '未指定'}；说明：{adj.note or '无'}")
    if not plan.color_adjustments:
        lines.append("- 无")
    lines.append("")

    lines.append(f"### {next_section}.3 局部调整")
    lines.append("")
    for adj in plan.local_adjustments or []:
        lines.append(f"- **{adj.target}**：{adj.value}（优先级 {adj.priority}）")
        lines.append(f"  - 理由：{adj.rationale}")
        if adj.software or adj.note:
            lines.append(f"  - 适用软件：{adj.software or '未指定'}；说明：{adj.note or '无'}")
    if not plan.local_adjustments:
        lines.append("- 无")
    lines.append("")

    lines.append(f"### {next_section}.4 不应破坏的艺术特征")
    lines.append("")
    for feature in plan.artistic_features_to_preserve or []:
        lines.append(f"- {feature}")
    if not plan.artistic_features_to_preserve:
        lines.append("- 无")
    lines.append("")

    lines.append(f"### {next_section}.5 关键词映射")
    lines.append("")
    for keyword, direction in (plan.intent_mapping or {}).items():
        lines.append(f"- `{keyword}`：{direction}")
    lines.append("")

    if plan.technical_issues:
        lines.append(f"### {next_section}.6 客观技术问题")
        lines.append("")
        for issue in plan.technical_issues:
            lines.append(f"- {issue}")
        lines.append("")

    if plan.warnings:
        lines.append(f"### {next_section}.7 风险提示")
        lines.append("")
        for warning in plan.warnings:
            lines.append(f"- {warning}")
        lines.append("")

    lines.append("---")
    lines.append("*本报告由 FrameSense V0.1 生成；AI 不会编造 EXIF 参数。*")
    return "\n".join(lines)


def export_markdown(
    filename: str,
    exif,
    stats,
    intent: IntentInput,
    plan: ColorGradingPlan,
    output_path: str | Path,
    references=None,
) -> Path:
    """将报告写入项目内路径（UTF-8）。"""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        build_markdown_report(filename, exif, stats, intent, plan, references),
        encoding="utf-8",
    )
    return output_path
