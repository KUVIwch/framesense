"""视觉模型能力验证模块测试（不发起真实网络请求）。"""
from __future__ import annotations

import json

from framesense.ai.capability import make_test_image, run_capability_test
from framesense.ai.vision import MockVisionClient


class FakeRealClient:
    """模拟真实客户端：返回受控内容，不联网。"""

    is_mock = False
    model = "fake-vision"
    base_url = "https://fake.example.com/v1"
    json_mode = True

    def __init__(self):
        self.last_usage = {"total_tokens": 10}
        self.last_duration_ms = 5
        self.calls = []

    def chat_with_meta(self, payload, preview=None, use_text_model=False):
        self.calls.append({"payload": payload, "preview": preview is not None})
        probe = str(payload.get("probe", ""))
        if "颜色" in probe and preview is not None:
            return "红色圆形", {"total_tokens": 5}, 10
        if "JSON" in probe:
            return '{"ok": true}', {"total_tokens": 5}, 10
        return "收到", {"total_tokens": 5}, 10


def test_make_test_image_known_colors():
    img = make_test_image()
    assert img.shape == (200, 320, 3)
    red_region = img[40:140, 60:160]
    assert (red_region[:, :, 0] > 150).any()
    assert (red_region[:, :, 1] < 100).any()
    green_region = img[80:160, 180:260]
    assert (green_region[:, :, 1] > 120).any()


def test_mock_client_skips_without_network():
    record = run_capability_test(MockVisionClient(), allow_real=True)
    assert record.errors
    assert record.vision_confirmed is False
    assert record.allow_real is True


def test_unauthorized_real_call_skipped(tmp_path):
    client = FakeRealClient()
    record = run_capability_test(client, allow_real=False, results_path=tmp_path / "r.json")
    assert any("未授权" in e for e in record.errors)
    assert client.calls == []
    assert (tmp_path / "r.json").exists()


def test_capability_records_vision_confirmed(tmp_path):
    client = FakeRealClient()
    record = run_capability_test(client, allow_real=True, results_path=tmp_path / "r.json")
    assert record.vision_confirmed is True
    assert record.json_mode_supported is True
    assert record.text_test["ok"] is True
    assert record.image_test["ok"] is True
    assert record.json_test["ok"] is True
    data = json.loads((tmp_path / "r.json").read_text(encoding="utf-8"))
    assert data[-1]["vision_confirmed"] is True


def test_capability_records_vision_not_confirmed(tmp_path):
    class NonVisionClient(FakeRealClient):
        def chat_with_meta(self, payload, preview=None, use_text_model=False):
            return "我不确定", {"total_tokens": 5}, 10

    record = run_capability_test(NonVisionClient(), allow_real=True, results_path=tmp_path / "r.json")
    assert record.vision_confirmed is False
