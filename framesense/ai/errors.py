"""视觉模型 API 错误分类与重试判定。"""
from __future__ import annotations

import json
from enum import Enum

from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AuthenticationError,
    RateLimitError,
)


class APIErrorKind(str, Enum):
    """API 错误类型。"""

    TIMEOUT = "timeout"
    AUTHENTICATION = "authentication"
    RATE_LIMIT = "rate_limit"
    SERVER_ERROR = "server_error"
    NETWORK = "network"
    INVALID_REQUEST = "invalid_request"
    PARSE = "parse"
    UNKNOWN = "unknown"


RETRYABLE_KINDS = {
    APIErrorKind.RATE_LIMIT,
    APIErrorKind.SERVER_ERROR,
    APIErrorKind.NETWORK,
}


def classify_api_error(exc: Exception) -> APIErrorKind:
    """将异常分类为可读的错误类型。"""
    if isinstance(exc, APITimeoutError):
        return APIErrorKind.TIMEOUT
    if isinstance(exc, AuthenticationError):
        return APIErrorKind.AUTHENTICATION
    if isinstance(exc, RateLimitError):
        return APIErrorKind.RATE_LIMIT
    if isinstance(exc, APIConnectionError):
        return APIErrorKind.NETWORK
    status = getattr(exc, "status_code", None)
    if status is None:
        response = getattr(exc, "response", None)
        status = getattr(response, "status_code", None)
    if status is not None:
        try:
            status = int(status)
        except (TypeError, ValueError):
            status = None
    if isinstance(exc, APIStatusError) or status is not None:
        if status == 429:
            return APIErrorKind.RATE_LIMIT
        if status in (401, 403):
            return APIErrorKind.AUTHENTICATION
        if status is not None and 400 <= status < 500:
            return APIErrorKind.INVALID_REQUEST
        if status is not None and status >= 500:
            return APIErrorKind.SERVER_ERROR
    if isinstance(exc, TimeoutError) or "timed out" in str(exc).lower():
        return APIErrorKind.TIMEOUT
    if isinstance(exc, json.JSONDecodeError):
        return APIErrorKind.PARSE
    return APIErrorKind.UNKNOWN


def is_retryable(exc: Exception) -> bool:
    """判断错误是否值得有限重试（限流/5xx/网络，不含超时与鉴权）。"""
    return classify_api_error(exc) in RETRYABLE_KINDS


def describe_error(exc: Exception) -> str:
    """返回带错误分类的描述，用于用户可见报错。"""
    return f"{classify_api_error(exc).value}: {exc}"
