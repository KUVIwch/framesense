"""调色决策流程：组合客观技术数据、创作意图、参考图统计与（可选）视觉模型。"""
from __future__ import annotations

import json
import logging
from typing import Any

from framesense.ai.vision import MockVisionClient, VisionModelClient
from framesense.grading.models import Adjustment, ColorGradingPlan, IntentInput

logger = logging.getLogger(__name__)

_DARK_MOODS = {"阴郁", "暗调", "神秘", "压抑", "忧郁", "孤寂", "暗黑"}
_BRIGHT_MOODS = {"明亮", "清新", "通透", "轻快", "欢快", "活力", "治愈", "高调"}
_WARM_MOODS = {"温暖", "复古", "日落", "怀旧", "胶片", "浓郁"}
_COOL_MOODS = {"冷清", "清冷", "科技感", "冷静", "蓝调"}
_LOW_SAT_MOODS = {"低饱和", "胶片", "复古", "阴郁", "神秘", "电影感"}

_REQUIRED_SCHEMA_EXAMPLE = {
    "summary": "整体方案摘要",
    "global_adjustments": [{"target": "曝光度", "value": "-0.3EV", "rationale": "理由", "priority": 2, "software": "Lightroom", "note": "说明"}],
    "color_adjustments": [{"target": "色温", "value": "+200K", "rationale": "理由", "priority": 2, "software": "Lightroom", "note": "说明"}],
    "local_adjustments": [{"target": "天空", "value": "渐变滤镜压暗", "rationale": "理由", "priority": 2, "software": "Photoshop ACR", "note": "说明"}],
    "artistic_features_to_preserve": ["保留的艺术特征"],
    "technical_issues": [],
    "intent_mapping": {"关键词": "处理方向"},
    "warnings": [],
    "model_provider": "openai",
    "confidence": 0.8,
}


def build_analysis_payload(stats, exif, intent: IntentInput, references=None) -> dict[str, Any]:
    """组装给模型的客观上下文（EXIF + 图像统计 + 创作意图 + 参考图统计）。"""
    refs = references or []
    return {
        "exif": exif.to_dict() if exif else {"source": "none"},
        "image_stats": _stats_to_dict(stats),
        "intent": {"keywords": intent.keywords, "custom_note": intent.custom_note},
        "reference_images": [_stats_to_dict(r) for r in refs],
    }


def _stats_to_dict(stats) -> dict[str, Any]:
    return {
        "width": stats.width,
        "height": stats.height,
        "histogram_normalized": stats.histogram_normalized,
        "percentiles": stats.percentiles,
        "shadow_ratio": stats.shadow_ratio,
        "midtone_ratio": stats.midtone_ratio,
        "highlight_ratio": stats.highlight_ratio,
        "mean_brightness": stats.mean_brightness,
        "brightness_std": stats.brightness_std,
        "contrast_rms": stats.contrast_rms,
        "mean_saturation": stats.mean_saturation,
        "mean_rgb": stats.mean_rgb,
        "dominant_colors": stats.dominant_colors,
        "color_cast": stats.color_cast,
        "edge_density": stats.edge_density,
    }


def generate_suggestion(
    stats,
    exif,
    intent: IntentInput,
    references=None,
    client: VisionModelClient | None = None,
    allow_upload: bool = False,
    preview=None,
) -> ColorGradingPlan:
    """生成调色建议。

    - 若 client 为 None 或 Mock 客户端：返回规则化 Mock 方案（明确标注 provider=mock）。
    - 否则调用真实视觉模型；任何失败都会抛出异常，绝不伪造分析结果。
    """
    if client is None or client.is_mock():
        return _mock_plan(stats, exif, intent, references)

    payload = build_analysis_payload(stats, exif, intent, references)
    image_to_send = preview if allow_upload else None
    content = ""
    try:
        content = client.chat(payload=payload, preview=image_to_send)
    except Exception as exc:
        logger.exception("视觉模型 API 调用失败")
        raise RuntimeError(f"调色建议生成失败（{type(exc).__name__}）：{exc}。未伪造分析结果。") from exc

    try:
        data = _extract_json_object(content)
        plan = ColorGradingPlan.model_validate(data)
        generation_status = "real"
    except Exception as format_exc:
        # 仅对格式/校验类错误执行一次有限修复尝试（使用文字整理模型）
        plan = _repair_plan(client, content, format_exc)
        if plan is None:
            raise RuntimeError(
                f"调色建议生成失败：模型输出格式校验未通过（{type(format_exc).__name__}）：{format_exc}。"
                "已尝试一次修复但失败，未伪造分析结果。"
            ) from format_exc
        generation_status = "repair"

    # 无论模型如何声明，真实调用统一标记为实际提供方
    plan.model_provider = "openai"
    plan.generation_status = generation_status
    plan.model_usage = getattr(client, "last_usage", None)
    plan.model_duration_ms = getattr(client, "last_duration_ms", None)
    return plan


def _repair_plan(
    client: VisionModelClient,
    invalid_content: str,
    error: Exception,
) -> ColorGradingPlan | None:
    """对格式错误的输出执行一次文字模型修复尝试；失败返回 None。"""
    repair_payload = {
        "task": "修复以下调色方案 JSON，使其严格符合给定字段结构。不要编造照片内容或 EXIF 参数。",
        "invalid_content": invalid_content,
        "validation_error": str(error),
        "required_schema": _REQUIRED_SCHEMA_EXAMPLE,
    }
    try:
        content = client.chat_with_meta(repair_payload, preview=None, use_text_model=True)[0]
        data = _extract_json_object(content)
        return ColorGradingPlan.model_validate(data)
    except Exception:
        return None


def _extract_json_object(content: str) -> dict[str, Any]:
    """从模型文本中提取 JSON 对象。"""
    text = content.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end > start:
            return json.loads(text[start : end + 1])
        raise ValueError("模型输出不是有效 JSON")


def _mock_plan(stats, exif, intent: IntentInput, references=None) -> ColorGradingPlan:
    """规则化 Mock 方案：基于客观统计与创作意图，明确标注为 Mock。"""
    keywords = intent.keywords
    plan = ColorGradingPlan(
        summary="【Mock 方案】基于客观统计与创作意图的规则化建议，未调用真实视觉模型。",
        model_provider="mock",
        confidence=0.4,
        generation_status="mock",
    )

    # 客观技术问题
    issues: list[str] = []
    if stats.shadow_ratio > 0.5 and stats.percentiles.get("p5", 0) < 20:
        issues.append("暗部占比过高且存在接近纯黑的像素，若为意外欠曝可考虑恢复阴影。")
    if stats.highlight_ratio > 0.1 and stats.percentiles.get("p95", 255) > 235:
        issues.append("亮部占比过高且高光接近溢出，需警惕高光细节丢失。")
    if stats.brightness_std < 25:
        issues.append("直方图分布集中，对比度偏低。")
    if stats.edge_density < 1.0:
        issues.append("边缘能量较低，画面可能偏柔或轻微失焦（需结合拍摄意图判断）。")
    plan.technical_issues = issues[:3]

    # 关键词映射
    for kw in keywords:
        if kw in _DARK_MOODS:
            plan.intent_mapping[kw] = "保留/强化暗部氛围，不盲目提亮"
        elif kw in _BRIGHT_MOODS:
            plan.intent_mapping[kw] = "适度提升通透感，但避免过曝"
        elif kw in _WARM_MOODS:
            plan.intent_mapping[kw] = "向暖色偏移，增强暖调质感"
        elif kw in _COOL_MOODS:
            plan.intent_mapping[kw] = "向冷色偏移，增强清冷氛围"
        elif kw in _LOW_SAT_MOODS:
            plan.intent_mapping[kw] = "控制饱和度，保留细腻层次"
        else:
            plan.intent_mapping[kw] = f"以「{kw}」为创意方向微调影调与色彩"

    dark = _DARK_MOODS.intersection(keywords)
    bright = _BRIGHT_MOODS.intersection(keywords)

    # 全局调整
    if dark:
        plan.global_adjustments.append(
            Adjustment(
                target="阴影",
                value="保持不变或轻微压暗",
                rationale="创作意图包含暗调/阴郁，暗部是艺术表达的一部分，不应自动提亮。",
                priority=1,
            )
        )
    elif stats.shadow_ratio > 0.5:
        plan.global_adjustments.append(
            Adjustment(
                target="阴影",
                value="轻微提升",
                rationale="暗部占比高且创作意图偏亮，适度恢复阴影细节。",
                priority=2,
            )
        )
    if stats.highlight_ratio > 0.1:
        plan.global_adjustments.append(
            Adjustment(
                target="高光",
                value="适度回落",
                rationale="高光接近溢出，优先保护高光细节。",
                priority=2,
            )
        )
    if stats.brightness_std < 25 and not dark:
        plan.global_adjustments.append(
            Adjustment(
                target="对比度",
                value="适度提升",
                rationale="直方图集中，对比度偏低。",
                priority=2,
            )
        )
    if not plan.global_adjustments:
        plan.global_adjustments.append(
            Adjustment(
                target="整体影调",
                value="轻微微调",
                rationale="客观数据无明显问题，以创作意图为准做轻微影调控制。",
                priority=3,
            )
        )

    # 色彩调整
    warm = _WARM_MOODS.intersection(keywords)
    cool = _COOL_MOODS.intersection(keywords)
    if warm:
        plan.color_adjustments.append(
            Adjustment(target="色温", value="向暖色偏移约 200-400K", rationale="增强温暖氛围。", priority=1)
        )
    elif cool:
        plan.color_adjustments.append(
            Adjustment(target="色温", value="向冷色偏移约 200-400K", rationale="增强清冷氛围。", priority=1)
        )
    if _LOW_SAT_MOODS.intersection(keywords):
        plan.color_adjustments.append(
            Adjustment(target="饱和度", value="整体轻微降低", rationale="低饱和情绪表达。", priority=2)
        )
    elif stats.mean_saturation < 0.1:
        plan.color_adjustments.append(
            Adjustment(
                target="饱和度",
                value="适度提升",
                rationale="画面饱和度偏低，若目标为高饱和表达可增强。",
                priority=3,
            )
        )
    if not plan.color_adjustments:
        plan.color_adjustments.append(
            Adjustment(target="色彩平衡", value="按中性基调微调", rationale="无强烈色偏时保持自然色彩。", priority=3)
        )

    # 局部调整
    if stats.shadow_ratio > 0.5 and not dark:
        plan.local_adjustments.append(
            Adjustment(
                target="暗部局部",
                value="蒙版局部提亮",
                rationale="只恢复必要暗部细节，避免整体提亮破坏氛围。",
                priority=2,
            )
        )
    if references:
        plan.local_adjustments.append(
            Adjustment(
                target="主体轮廓",
                value="参考图风格匹配",
                rationale="参考图存在时优先匹配参考作品的影调关系。",
                priority=2,
            )
        )

    # 不应破坏的艺术特征
    preserve = ["保留原始构图与裁切", "避免一键美颜与过度平滑"]
    if dark:
        preserve.append("保留暗部层次、颗粒感与低光氛围")
    if stats.highlight_ratio > 0.1:
        preserve.append("保留高光处的有意溢出（若为创作选择）")
    if stats.mean_saturation < 0.15:
        preserve.append("保留低饱和的细腻过渡")
    plan.artistic_features_to_preserve = preserve

    # 参考图提示
    if references:
        plan.summary += f" 已纳入 {len(references)} 张参考图的统计特征。"
    for group in (plan.global_adjustments, plan.color_adjustments, plan.local_adjustments):
        for adj in group:
            if not adj.software:
                adj.software = "Lightroom/Photoshop ACR"
            if not adj.note:
                adj.note = "Mock 规则建议，请以实际画面为准。"
    return plan
