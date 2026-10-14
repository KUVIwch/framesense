"""配置加载测试。"""
from __future__ import annotations

import pytest

from framesense.config import load_config


def test_default_mode_is_mock(monkeypatch, tmp_path):
    monkeypatch.delenv("FRAMESENSE_AI_MODE", raising=False)
    monkeypatch.delenv("UNISOUND_API_KEY", raising=False)
    monkeypatch.delenv("UNISOUND_API_BASE_URL", raising=False)
    monkeypatch.delenv("UNISOUND_MODEL", raising=False)
    cfg = load_config(env_path=tmp_path / "nonexistent.env")
    assert cfg.ai_mode == "mock"
    assert cfg.unisound_api_key == ""


def test_explicit_mode_wins(monkeypatch, tmp_path):
    monkeypatch.setenv("FRAMESENSE_AI_MODE", "unisound")
    cfg = load_config(env_path=tmp_path / "nonexistent.env", ai_mode="mock")
    assert cfg.ai_mode == "mock"


def test_invalid_mode_raises(tmp_path):
    with pytest.raises(ValueError):
        load_config(env_path=tmp_path / "nonexistent.env", ai_mode="bad")


def test_env_file_loading(monkeypatch, tmp_path):
    monkeypatch.delenv("FRAMESENSE_AI_MODE", raising=False)
    monkeypatch.delenv("UNISOUND_API_KEY", raising=False)
    monkeypatch.delenv("UNISOUND_API_BASE_URL", raising=False)
    monkeypatch.delenv("UNISOUND_MODEL", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text(
        "UNISOUND_API_KEY=test-key-123\nFRAMESENSE_AI_MODE=unisound\n",
        encoding="utf-8",
    )
    cfg = load_config(env_path=env_file)
    assert cfg.unisound_api_key == "test-key-123"
    assert cfg.ai_mode == "unisound"


def test_openai_text_model_reasoning_db_path(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENAI_TEXT_MODEL", "text-model-1")
    monkeypatch.setenv("FRAMESENSE_REASONING_EFFORT", "low")
    monkeypatch.setenv("FRAMESENSE_DB_PATH", str(tmp_path / "x.db"))
    cfg = load_config(env_path=tmp_path / "nonexistent.env")
    assert cfg.openai_text_model == "text-model-1"
    assert cfg.reasoning_effort == "low"
    assert cfg.db_path == str(tmp_path / "x.db")


def test_invalid_reasoning_effort_raises(monkeypatch, tmp_path):
    monkeypatch.setenv("FRAMESENSE_REASONING_EFFORT", "extreme")
    with pytest.raises(ValueError):
        load_config(env_path=tmp_path / "nonexistent.env")
