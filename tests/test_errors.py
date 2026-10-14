"""API 错误分类测试。"""
from __future__ import annotations

import json

from framesense.ai.errors import (
    APIErrorKind,
    classify_api_error,
    describe_error,
    is_retryable,
)


class _FakeStatusError(Exception):
    def __init__(self, status_code: int):
        super().__init__(f"fake status {status_code}")
        self.status_code = status_code


def test_classify_timeout_by_message():
    err = TimeoutError("Request timed out.")
    assert classify_api_error(err) == APIErrorKind.TIMEOUT


def test_classify_status_500():
    assert classify_api_error(_FakeStatusError(500)) == APIErrorKind.SERVER_ERROR


def test_classify_status_429():
    assert classify_api_error(_FakeStatusError(429)) == APIErrorKind.RATE_LIMIT


def test_classify_status_401():
    assert classify_api_error(_FakeStatusError(401)) == APIErrorKind.AUTHENTICATION


def test_classify_status_400():
    assert classify_api_error(_FakeStatusError(400)) == APIErrorKind.INVALID_REQUEST


def test_classify_parse_error():
    assert classify_api_error(json.JSONDecodeError("bad json", "doc", 0)) == APIErrorKind.PARSE


def test_classify_unknown():
    assert classify_api_error(ValueError("boom")) == APIErrorKind.UNKNOWN


def test_retryable_only_for_transient_errors():
    assert is_retryable(_FakeStatusError(500)) is True
    assert is_retryable(_FakeStatusError(429)) is True
    assert is_retryable(TimeoutError("timed out")) is False
    assert is_retryable(_FakeStatusError(401)) is False
    assert is_retryable(_FakeStatusError(400)) is False


def test_describe_error_contains_kind():
    assert "server_error" in describe_error(_FakeStatusError(500))
