"""FrameSense V0.2 · 摄影分析与调色建议（Streamlit 本地 Web 应用）。

运行方式（项目根目录）：
    .venv\\Scripts\\streamlit run framesense/web/app.py

安全约束：
- 上传文件仅在内存中处理，绝不写回用户原文件。
- RAW 默认只在本地解码；上传预览图到云模型前必须勾选授权。
- API Key 仅从环境变量 / .env 读取，不写入历史记录或报告。
"""
from __future__ import annotations

import numpy as np
import streamlit as st
from pathlib import Path

from framesense.analysis.exif import ExifData, read_exif_bytes
from framesense.analysis.loader import load_image_bytes, make_preview
from framesense.analysis.stats import compute_image_stats
from framesense.ai.capability import run_capability_test
from framesense.ai.vision import create_vision_client
from framesense.config import load_config
from framesense.db import get_session, list_sessions, save_session
from framesense.export import build_markdown_report
from framesense.grading.decision import generate_suggestion
from framesense.grading.models import IntentInput

st.set_page_config(page_title="FrameSense V0.2", page_icon="🎨", layout="wide")
st.title("🎨 FrameSense V0.2 · 摄影分析与调色建议")
st.caption("本地优先：RAW 只在本地解码；上传预览图到云模型前必须获得你的确认。")


def _code_fingerprint() -> str:
    """计算核心源码最新修改时间，用于检测服务进程是否使用旧模块缓存。"""
    root = Path(__file__).resolve().parent.parent
    files = sorted((root / "framesense").rglob("*.py"))
    latest = max((f.stat().st_mtime_ns for f in files), default=0)
    return str(latest)


_CODE_FINGERPRINT = _code_fingerprint()

EMOTION_OPTIONS = [
    "明亮",
    "清新",
    "温暖",
    "复古",
    "电影感",
    "阴郁",
    "神秘",
    "冷清",
    "活力",
    "治愈",
    "浓郁",
    "低饱和",
    "高饱和",
    "通透",
    "怀旧",
    "胶片",
    "蓝调",
    "暗调",
]

EXIF_LABELS = [
    ("相机厂商", "make"),
    ("相机型号", "model"),
    ("镜头", "lens_model"),
    ("ISO", "iso"),
    ("快门速度", "shutter_speed"),
    ("光圈", "aperture"),
    ("焦距", "focal_length"),
    ("曝光补偿", "exposure_bias"),
    ("白平衡", "white_balance"),
    ("拍摄时间", "taken_at"),
]


def render_exif_table(exif: ExifData | None) -> None:
    """展示可用 EXIF；缺失字段不显示、不编造。"""
    st.markdown("**可用 EXIF 数据**")
    if exif is None:
        st.info("无法读取 EXIF 数据。")
        return
    rows = []
    for label, attr in EXIF_LABELS:
        value = getattr(exif, attr, None)
        if value is not None:
            rows.append({"字段": label, "值": str(value)})
    if rows:
        st.table(rows)
        st.caption(f"EXIF 来源：{exif.source}")
    else:
        st.info("文件中未读取到 EXIF 拍摄参数，以下分析不会包含任何 EXIF 推断。")


def render_stats(stats) -> None:
    """展示客观图像统计。"""
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("平均亮度", f"{stats.mean_brightness:.0f}/255")
    c2.metric("暗部占比", f"{stats.shadow_ratio * 100:.1f}%")
    c3.metric("中间调占比", f"{stats.midtone_ratio * 100:.1f}%")
    c4.metric("亮部占比", f"{stats.highlight_ratio * 100:.1f}%")
    st.markdown("**亮度直方图**")
    st.line_chart(np.asarray(stats.histogram_normalized, dtype=np.float64))
    st.caption(
        f"标准差 {stats.brightness_std:.1f} · 平均饱和度 {stats.mean_saturation:.3f} · "
        f"清晰度代理(边缘能量) {stats.edge_density:.2f} · 主色 "
        + ", ".join(f"{c['hex']}({c['ratio'] * 100:.0f}%)" for c in stats.dominant_colors[:4])
    )


def render_plan(plan) -> None:
    """展示调色方案。"""
    if plan.model_provider == "mock":
        st.info("当前为 **Mock 规则方案**（未调用真实视觉模型）。配置 OPENAI_API_KEY 后可切换真实模型。")
    st.caption(
        f"生成状态：{plan.generation_status}（real=真实模型 / mock=规则方案 / repair=经一次修复）"
    )
    if plan.model_duration_ms is not None:
        st.caption(f"模型耗时：{plan.model_duration_ms} ms")
    if plan.model_usage:
        st.caption(f"Token 用量：{plan.model_usage}")
    st.markdown(plan.summary)

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**全局调整**")
        for adj in plan.global_adjustments:
            st.markdown(f"- **{adj.target}**：{adj.value}（优先级 {adj.priority}）")
            st.markdown(f"  - 理由：{adj.rationale}")
            st.markdown(f"  - 适用软件：{adj.software or '未指定'}；说明：{adj.note or '无'}")
        if not plan.global_adjustments:
            st.caption("无")
        st.markdown("**色彩调整**")
        for adj in plan.color_adjustments:
            st.markdown(f"- **{adj.target}**：{adj.value}（优先级 {adj.priority}）")
            st.markdown(f"  - 理由：{adj.rationale}")
            st.markdown(f"  - 适用软件：{adj.software or '未指定'}；说明：{adj.note or '无'}")
        if not plan.color_adjustments:
            st.caption("无")
    with col2:
        st.markdown("**局部调整**")
        for adj in plan.local_adjustments:
            st.markdown(f"- **{adj.target}**：{adj.value}（优先级 {adj.priority}）")
            st.markdown(f"  - 理由：{adj.rationale}")
            st.markdown(f"  - 适用软件：{adj.software or '未指定'}；说明：{adj.note or '无'}")
        if not plan.local_adjustments:
            st.caption("无")

    st.markdown("**不应破坏的艺术特征**")
    for feature in plan.artistic_features_to_preserve:
        st.markdown(f"- {feature}")
    st.markdown("**客观技术问题**")
    for issue in plan.technical_issues:
        st.markdown(f"- {issue}")
    st.markdown("**关键词映射**")
    for keyword, direction in plan.intent_mapping.items():
        st.markdown(f"- `{keyword}`：{direction}")


def main() -> None:
    config = load_config()

    # ---------- 侧边栏 ----------
    with st.sidebar:
        if _code_fingerprint() != _CODE_FINGERPRINT:
            st.warning("检测到代码文件已更新，当前进程仍使用旧模块缓存。请重启应用（start_web.bat）后生效。")
        st.header("⚙️ 模型与隐私")
        st.info(
            f"视觉模式：**{config.vision_mode}**\n\n"
            "API Key 仅从环境变量 / `.env` 读取。"
        )
        if config.vision_mode == "openai" and not config.openai_api_key:
            st.warning("已配置 openai 模式，但缺少 OPENAI_API_KEY，将自动使用 Mock。")
        allow_upload = st.checkbox(
            "允许将缩小后的预览图上传到云端视觉模型",
            value=False,
            help="必须显式勾选；RAW 原图不会上传，只会上传最长边 ≤1024 像素的 JPEG 预览。",
        )
        st.divider()
        st.subheader("🧪 自定义模型 API（可选）")
        use_custom = st.checkbox(
            "使用自定义 API（Key 不落盘）",
            value=False,
            help="填写的 Base URL / API Key / 模型名仅用于本次生成，不保存到 .env、不写入历史。",
        )
        custom_base_url = ""
        custom_api_key = ""
        custom_model = ""
        if use_custom:
            custom_base_url = st.text_input("API Base URL", placeholder="https://maas-api.unisound.com/v1")
            custom_api_key = st.text_input("API Key", type="password", placeholder="sk-...")
            custom_model = st.text_input("模型名", placeholder="u2 或 u2-flash")
            st.caption("三项都要填写；Key 仅存在当前页面内存中。")
        st.divider()
        st.subheader("⚡ 模型与速度")
        model_preset = st.selectbox(
            "云知声模型模板",
            ["u2-flash（默认）", "u2（更快）", "u2-med（均衡）", "自定义（在上方填写）"],
            index=0,
            help="选择模板可切换模型名；若已启用自定义 API，以自定义填写为准。",
        )
        preview_size = st.select_slider(
            "云端预览图边长（像素）",
            options=[512, 768, 1024],
            value=768,
            help="越小越快、越省流量；仅当勾选上传授权时生效。",
        )
        if use_custom:
            custom_config = {
                "api_key": custom_api_key,
                "base_url": custom_base_url,
                "model": custom_model,
            }
        else:
            custom_config = None
            preset_model = {
                "u2-flash（默认）": "u2-flash",
                "u2（更快）": "u2",
                "u2-med（均衡）": "u2-med",
            }.get(model_preset)
            if preset_model and config.vision_mode == "openai" and config.openai_api_key:
                custom_config = {
                    "api_key": config.openai_api_key,
                    "base_url": config.openai_base_url,
                    "model": preset_model,
                }
        st.divider()
        st.subheader("🧪 模型能力测试")
        authorize_test = st.checkbox(
            "我授权执行一次真实模型测试（产生少量费用）",
            value=False,
            help="测试会用合成图片调用模型 3 次（文本/图片/JSON），验证模型是否真的理解图像。默认不执行。",
        )
        if st.button("测试当前模型（文本/图片/JSON）"):
            if not authorize_test:
                st.error("真实模型测试默认关闭，请先勾选授权。")
            else:
                try:
                    client = create_vision_client(config, custom=custom_config)
                    with st.spinner("正在执行能力测试（可能需要 1-3 分钟）..."):
                        record = run_capability_test(client, allow_real=True)
                    st.write(f"模型：{record.model}")
                    st.write(f"图片理解确认：{'是 ✅' if record.vision_confirmed else '否 ❌'}")
                    st.write(f"JSON 兼容：{'是' if record.json_mode_supported else '否'}")
                    if record.text_test:
                        st.write(f"文本测试：{'通过' if record.text_test.get('ok') else '失败'}")
                    if record.image_test:
                        st.write(f"图片测试：{'通过' if record.image_test.get('ok') else '失败'}")
                    if record.errors:
                        st.error(f"错误：{record.errors}")
                    st.caption("结果已保存到 data/vision_capability_results.json")
                except Exception as exc:
                    st.error(f"能力测试失败：{exc}")
        st.divider()
        st.subheader("🕘 历史记录")
        sessions = list_sessions(limit=20)
        if sessions:
            selected = st.selectbox(
                "选择历史会话",
                sessions,
                format_func=lambda r: f"#{r['id']} {r['created_at']} {r['filename']}",
            )
            if st.button("加载所选会话"):
                st.session_state["history_id"] = selected["id"]
        else:
            st.caption("暂无历史记录")

    # ---------- 上传照片 ----------
    uploaded = st.file_uploader(
        "上传照片（JPG / PNG / Sony ARW）",
        type=["jpg", "jpeg", "png", "arw"],
    )
    if uploaded is None:
        st.info("请先上传一张照片，然后选择创作意图生成调色建议。")
        return

    data = uploaded.getvalue()
    filename = uploaded.name
    try:
        loaded = load_image_bytes(data, filename, source_label=filename)
        st.image(loaded.rgb, caption=f"{filename} · {loaded.width}x{loaded.height} · {loaded.format}", width="stretch")
    except Exception as exc:
        st.error(f"图片读取失败：{exc}")
        return

    try:
        exif = read_exif_bytes(data, filename)
    except Exception:
        exif = None

    stats = compute_image_stats(loaded.rgb)

    # ---------- 创作意图 ----------
    st.divider()
    st.subheader("🎯 创作意图")
    selected_keywords = st.multiselect(
        "选择情绪关键词（1-3 个）",
        EMOTION_OPTIONS,
        default=["电影感"],
    )
    custom_keyword = st.text_input("自定义关键词（可选，计入总数）", "")
    keywords = [k.strip() for k in selected_keywords + ([custom_keyword] if custom_keyword.strip() else [])]
    if not keywords:
        st.warning("请至少选择 1 个情绪关键词。")
    elif len(keywords) > 3:
        st.warning("最多 3 个情绪关键词，请减少选择。")
    st.caption(f"当前关键词：{'、'.join(keywords)}")

    # ---------- 参考作品 ----------
    st.subheader("🖼️ 参考作品（可选，1-3 张）")
    refs = st.file_uploader(
        "上传参考作品",
        type=["jpg", "jpeg", "png"],
        accept_multiple_files=True,
    )
    if len(refs) > 3:
        st.warning("最多 3 张参考作品，超出部分将被忽略。")
        refs = refs[:3]
    ref_stats = []
    ref_cols = st.columns(max(1, len(refs)))
    for idx, ref_file in enumerate(refs[:3]):
        try:
            ref_loaded = load_image_bytes(ref_file.getvalue(), ref_file.name)
            ref_stats.append(compute_image_stats(ref_loaded.rgb))
            with ref_cols[idx]:
                st.image(ref_loaded.rgb, caption=ref_file.name, width="stretch")
        except Exception as exc:
            st.warning(f"参考图 {ref_file.name} 读取失败：{exc}")

    # ---------- 客观分析展示 ----------
    st.divider()
    st.subheader("📊 客观图像分析")
    render_exif_table(exif)
    render_stats(stats)

    # ---------- 生成调色建议 ----------
    st.divider()
    st.subheader("🎨 调色建议")
    can_generate = 1 <= len(keywords) <= 3
    if st.button("生成调色建议", type="primary", disabled=not can_generate):
        if not can_generate:
            st.error("请选择 1-3 个情绪关键词。")
            return
        intent = IntentInput(keywords=keywords)

        if use_custom and not (custom_api_key and custom_base_url and custom_model):
            st.error("请填写完整的自定义 API 配置（Base URL / API Key / 模型名）。")
            return

        try:
            client = create_vision_client(config, custom=custom_config)
        except ValueError as exc:
            st.error(str(exc))
            return

        preview = make_preview(loaded.rgb, max_side=preview_size) if allow_upload else None
        try:
            with st.status("正在生成调色方案...", expanded=True) as status:
                st.write("① 文件读取与 EXIF 解析完成")
                st.write("② 客观图像统计完成")
                st.write("③ 正在调用视觉模型（图片 + 统计数据），可能需要 1-3 分钟...")
                plan = generate_suggestion(
                    stats=stats,
                    exif=exif,
                    intent=intent,
                    references=ref_stats or None,
                    client=client,
                    allow_upload=allow_upload,
                    preview=preview,
                )
                st.write("④ 模型输出已通过 Pydantic 校验")
                status.update(label="调色方案生成完成", state="complete")
        except Exception as exc:
            st.error(f"生成失败：{exc}")
            return

        report_md = build_markdown_report(
            filename=filename,
            exif=exif,
            stats=stats,
            intent=intent,
            plan=plan,
            references=ref_stats or None,
        )
        source_json = {
            "filename": filename,
            "exif": exif.to_dict() if exif else {"source": "none"},
            "stats": {
                "width": stats.width,
                "height": stats.height,
                "mean_brightness": stats.mean_brightness,
                "shadow_ratio": stats.shadow_ratio,
                "highlight_ratio": stats.highlight_ratio,
            },
            "intent_keywords": intent.keywords,
        }
        try:
            session_id = save_session(
                filename=filename,
                intent_keywords=intent.keywords,
                plan_json=plan.model_dump(),
                report_md=report_md,
                source_json=source_json,
            )
            st.session_state["session_id"] = session_id
        except Exception:
            st.session_state["session_id"] = None

        st.session_state["plan"] = plan
        st.session_state["report_md"] = report_md

    # ---------- 展示结果 ----------
    if "plan" in st.session_state:
        st.divider()
        render_plan(st.session_state["plan"])
        st.download_button(
            "⬇️ 导出 Markdown 报告",
            data=st.session_state.get("report_md", ""),
            file_name=f"framesense_report_{st.session_state.get('session_id', '')}.md",
            mime="text/markdown",
        )
        if st.session_state.get("session_id"):
            st.caption(f"已保存到本地历史记录 #{st.session_state['session_id']}。")

    # ---------- 历史会话查看 ----------
    if st.session_state.get("history_id"):
        row = get_session(st.session_state["history_id"])
        if row:
            st.divider()
            st.subheader(f"🕘 历史会话 #{row['id']}（{row['created_at']}）")
            st.markdown(f"**源文件**：{row['filename']}")
            st.markdown(f"**关键词**：{row['intent_keywords']}")
            st.markdown(f"**调色方案**：{row['plan_json']}")
            st.download_button(
                "⬇️ 导出该历史会话 Markdown",
                data=row["report_md"],
                file_name=f"framesense_history_{row['id']}.md",
                mime="text/markdown",
            )


if __name__ == "__main__":
    main()
