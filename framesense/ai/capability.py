"""视觉模型能力验证模块。

通过程序生成的已知内容图片，验证模型是否真正理解图像内容。
仅凭 HTTP 200 或返回 JSON 不足以证明视觉能力；本模块用「图中有红圆+绿矩形」
这类已知事实来检验模型是否真的“看到”了图片。

安全约束：真实模型测试默认关闭（allow_real=False），必须显式授权才执行付费调用。
"""
from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw

from framesense.ai.vision import MockVisionClient, VisionModelClient
from framesense.grading.decision import _extract_json_object

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_RESULTS_PATH = PROJECT_ROOT / "data" / "vision_capability_results.json"


def make_test_image(size: tuple[int, int] = (320, 200)) -> np.ndarray:
    """生成内容已知的合成测试图：蓝色背景 + 红色圆形 + 绿色矩形。"""
    img = Image.new("RGB", size, (40, 90, 200))
    draw = ImageDraw.Draw(img)
    draw.ellipse([60, 40, 160, 140], fill=(220, 50, 50))
    draw.rectangle([180, 80, 260, 160], fill=(60, 180, 80))
    return np.asarray(img, dtype=np.uint8)


@dataclass
class CapabilityRecord:
    """单次能力验证结果。"""

    model: str
    base_url: str
    started_at: str
    allow_real: bool = False
    duration_ms: int = 0
    text_test: dict[str, Any] | None = None
    image_test: dict[str, Any] | None = None
    json_test: dict[str, Any] | None = None
    vision_confirmed: bool = False
    json_mode_supported: bool = False
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _save_records(records: list[CapabilityRecord], results_path: str | Path) -> Path:
    path = Path(results_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    existing: list[dict[str, Any]] = []
    if path.exists():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            existing = []
    existing.append(records[-1].to_dict())
    path.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def run_capability_test(
    client: VisionModelClient,
    allow_real: bool = False,
    results_path: str | Path = DEFAULT_RESULTS_PATH,
) -> CapabilityRecord:
    """运行能力验证并保存结果。

    Args:
        client: 视觉模型客户端（Mock 客户端不会被调用）。
        allow_real: 是否授权发起真实付费调用。默认 False，仅生成“已跳过”记录。
        results_path: 结果保存路径。
    """
    start_time = time.monotonic()
    record = CapabilityRecord(
        model=getattr(client, "model", "unknown"),
        base_url=getattr(client, "base_url", ""),
        started_at=_now(),
        allow_real=allow_real,
    )
    if client is None or isinstance(client, MockVisionClient):
        record.errors.append("客户端为 Mock，不能执行真实能力验证。")
        _save_records([record], results_path)
        return record
    if not allow_real:
        record.errors.append("未授权真实调用，能力验证已跳过（allow_real=False）。")
        _save_records([record], results_path)
        return record

    try:
        # 1) 文本输入测试
        content, usage, duration = client.chat_with_meta(
            {"probe": "请只回复两个字：收到"}, use_text_model=False
        )
        record.text_test = {
            "ok": bool(content and content.strip()),
            "content_excerpt": (content or "").strip()[:80],
            "usage": usage,
            "duration_ms": duration,
        }

        # 2) 图片输入测试：红圆 + 绿矩形
        preview = make_test_image()
        content, usage, duration = client.chat_with_meta(
            {"probe": "图中最大的圆形是什么颜色？请只回答颜色名称。"},
            preview=preview,
        )
        lowered = (content or "").lower()
        record.image_test = {
            "ok": bool(content and content.strip()),
            "content_excerpt": (content or "").strip()[:80],
            "usage": usage,
            "duration_ms": duration,
        }
        record.vision_confirmed = any(k in lowered for k in ["红", "red"]) and any(
            k in lowered for k in ["圆", "circle", "圆形"]
        )

        # 3) JSON 兼容性测试
        content, usage, duration = client.chat_with_meta(
            {"probe": "只输出 JSON：{\"ok\": true}"}, use_text_model=False
        )
        try:
            parsed = _extract_json_object(content or "")
            json_ok = isinstance(parsed, dict)
        except Exception:
            json_ok = False
        record.json_test = {
            "response_format_used": client.json_mode,
            "ok": json_ok,
            "content_excerpt": (content or "").strip()[:80],
            "usage": usage,
            "duration_ms": duration,
        }
        record.json_mode_supported = json_ok
    except Exception as exc:
        record.errors.append(f"{type(exc).__name__}: {exc}")

    record.duration_ms = int((time.monotonic() - start_time) * 1000)
    _save_records([record], results_path)
    return record
