"""报告生成与保存。"""
from __future__ import annotations

import json
from pathlib import Path

from framesense.models import SequenceReport


def report_to_dict(report: SequenceReport) -> dict:
    """报告转字典。"""
    return report.to_dict()


def save_json(report: SequenceReport, output_path: Path) -> Path:
    """保存 JSON 报告（UTF-8）。"""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return output_path


def to_markdown(report: SequenceReport) -> str:
    """渲染 Markdown 报告。"""
    lines: list[str] = []
    lines.append(f"# {report.title}")
    lines.append("")
    lines.append(f"- 生成时间：{report.generated_at}")
    lines.append(f"- 来源目录：`{report.source_path}`")
    lines.append(f"- 帧数：{report.total_frames}")
    lines.append(f"- AI 模式：{report.ai_mode}（模型：{report.ai_model or '无'}）")
    lines.append(f"- 关键帧阈值：{report.threshold}")
    lines.append("")
    lines.append("## 总体摘要")
    lines.append("")
    lines.append(report.overall_summary)
    lines.append("")
    lines.append("## 帧详情")
    lines.append("")
    lines.append("| 索引 | 文件名 | 尺寸 | 亮度 | 饱和度 | 关键帧 | AI 摘要 |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- |")
    for f in report.frames:
        ai_summary = (f.ai.summary if f.ai else "") or ""
        ai_summary = ai_summary.replace("|", "\\|").replace("\n", " ")
        lines.append(
            f"| {f.index} | {f.filename} | {f.features.width}x{f.features.height} "
            f"| {f.features.mean_brightness:.0f} | {f.features.mean_saturation:.2f} "
            f"| {'是' if f.is_keyframe else '否'} | {ai_summary} |"
        )
    lines.append("")
    lines.append("## 帧间差异")
    lines.append("")
    if report.pair_diffs:
        lines.append("| 帧A | 帧B | MAE | RMSE | 直方图距离 | 差异分 | 类型 |")
        lines.append("| --- | --- | --- | --- | --- | --- | --- |")
        for d in report.pair_diffs:
            lines.append(
                f"| {d.filename_a} | {d.filename_b} | {d.mae:.2f} | {d.rmse:.2f} "
                f"| {d.histogram_distance:.3f} | {d.diff_score:.3f} | {d.note} |"
            )
    else:
        lines.append("（无相邻帧对比数据）")
    lines.append("")
    lines.append("## 备注")
    lines.append("")
    for n in report.notes:
        lines.append(f"- {n}")
    if not report.notes:
        lines.append("- 无")
    lines.append("")
    return "\n".join(lines)


def save_markdown(report: SequenceReport, output_path: Path) -> Path:
    """保存 Markdown 报告（UTF-8）。"""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(to_markdown(report), encoding="utf-8")
    return output_path
