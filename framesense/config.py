"""配置加载：.env 与环境变量。"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ENV_PATH = PROJECT_ROOT / ".env"

AI_MODE_MOCK = "mock"
AI_MODE_UNISOUND = "unisound"
VALID_AI_MODES = {AI_MODE_MOCK, AI_MODE_UNISOUND}

VISION_MODE_MOCK = "mock"
VISION_MODE_OPENAI = "openai"
VALID_VISION_MODES = {VISION_MODE_MOCK, VISION_MODE_OPENAI}
VALID_REASONING_EFFORTS = {"", "none", "low", "medium", "high"}


@dataclass(frozen=True)
class AppConfig:
    """应用配置。"""

    ai_mode: str = AI_MODE_MOCK
    unisound_api_key: str = ""
    unisound_api_base_url: str = ""
    unisound_model: str = ""
    request_timeout_seconds: float = 30.0
    max_retries: int = 2
    vision_mode: str = VISION_MODE_MOCK
    openai_api_key: str = ""
    openai_base_url: str = ""
    openai_model: str = ""
    openai_json_mode: bool = True
    openai_max_tokens: int = 4000
    openai_text_model: str = ""
    reasoning_effort: str = ""
    db_path: str = ""


def load_config(env_path: Path | None = None, ai_mode: str | None = None) -> AppConfig:
    """加载 .env（若存在）与显式参数，组装配置。

    Args:
        env_path: .env 文件路径，默认项目根目录。
        ai_mode: 显式指定的 AI 模式，优先级高于环境变量。

    Raises:
        ValueError: AI 模式不合法时。
    """
    env_path = env_path or DEFAULT_ENV_PATH
    if env_path.exists():
        load_dotenv(env_path, override=False)

    mode = (ai_mode or os.getenv("FRAMESENSE_AI_MODE") or AI_MODE_MOCK).strip().lower()
    if mode not in VALID_AI_MODES:
        raise ValueError(f"无效的 AI 模式: {mode!r}，可选值: {sorted(VALID_AI_MODES)}")

    vision_mode = (os.getenv("FRAMESENSE_VISION_MODE") or VISION_MODE_MOCK).strip().lower()
    if vision_mode not in VALID_VISION_MODES:
        raise ValueError(f"无效的视觉模型模式: {vision_mode!r}，可选值: {sorted(VALID_VISION_MODES)}")

    json_mode_raw = os.getenv("FRAMESENSE_JSON_MODE", "true").strip().lower()
    json_mode = json_mode_raw in {"1", "true", "yes", "on"}
    reasoning_effort = os.getenv("FRAMESENSE_REASONING_EFFORT", "").strip().lower()
    if reasoning_effort not in VALID_REASONING_EFFORTS:
        raise ValueError(
            f"无效的 FRAMESENSE_REASONING_EFFORT: {reasoning_effort!r}，"
            f"可选: {sorted(VALID_REASONING_EFFORTS - {''})}"
        )

    return AppConfig(
        ai_mode=mode,
        unisound_api_key=os.getenv("UNISOUND_API_KEY", "").strip(),
        unisound_api_base_url=os.getenv("UNISOUND_API_BASE_URL", "").strip(),
        unisound_model=os.getenv("UNISOUND_MODEL", "").strip(),
        request_timeout_seconds=float(os.getenv("FRAMESENSE_REQUEST_TIMEOUT", "30")),
        max_retries=int(os.getenv("FRAMESENSE_MAX_RETRIES", "2")),
        vision_mode=vision_mode,
        openai_api_key=os.getenv("OPENAI_API_KEY", "").strip(),
        openai_base_url=os.getenv("OPENAI_BASE_URL", "").strip(),
        openai_model=os.getenv("OPENAI_MODEL", "").strip(),
        openai_json_mode=json_mode,
        openai_max_tokens=int(os.getenv("FRAMESENSE_MAX_TOKENS", "4000")),
        openai_text_model=os.getenv("OPENAI_TEXT_MODEL", "").strip(),
        reasoning_effort=reasoning_effort,
        db_path=os.getenv("FRAMESENSE_DB_PATH", "").strip(),
    )
