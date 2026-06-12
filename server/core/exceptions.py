"""业务异常层 — 让服务层脱离 FastAPI 依赖。

服务层抛出 `DomainException` 子类，路由层（main.py 注册的全局处理器）
将异常统一转换为 HTTP 响应。服务层不再需要 `from fastapi import HTTPException`。

迁移策略：
- 新代码直接 raise `DomainException` 子类。
- 旧代码暂时保留 HTTPException，逐步替换。
"""
from __future__ import annotations

from typing import Any

from fastapi import status as _status


class DomainException(Exception):
    """所有业务异常的基类。

    子类通过覆盖 `status_code` 和 `default_detail` 自定义 HTTP 表现。
    服务层代码在抛出时也可以通过 `detail` 字段覆盖默认消息。
    """

    status_code: int = _status.HTTP_500_INTERNAL_SERVER_ERROR
    default_detail: str = "服务器内部错误"

    def __init__(self, detail: str | None = None, *, extra: dict[str, Any] | None = None) -> None:
        self.detail = detail or self.default_detail
        self.extra = extra or {}
        super().__init__(self.detail)


class AuthException(DomainException):
    """认证失败（401）。"""

    status_code = _status.HTTP_401_UNAUTHORIZED
    default_detail = "未认证"


class ForbiddenException(DomainException):
    """权限不足（403）。"""

    status_code = _status.HTTP_403_FORBIDDEN
    default_detail = "权限不足"


class ValidationException(DomainException):
    """输入校验失败（400）。"""

    status_code = _status.HTTP_400_BAD_REQUEST
    default_detail = "请求参数无效"


class NotFoundException(DomainException):
    """资源不存在（404）。"""

    status_code = _status.HTTP_404_NOT_FOUND
    default_detail = "资源不存在"


class ConflictException(DomainException):
    """资源冲突（409）。"""

    status_code = _status.HTTP_409_CONFLICT
    default_detail = "资源冲突"


class RateLimitException(DomainException):
    """请求频率超限（429）。"""

    status_code = _status.HTTP_429_TOO_MANY_REQUESTS
    default_detail = "请求过于频繁，请稍后再试"


class ConfigurationException(DomainException):
    """服务配置缺失或无效（500）。"""

    status_code = _status.HTTP_500_INTERNAL_SERVER_ERROR
    default_detail = "服务配置错误"


class ServiceUnavailableException(DomainException):
    """依赖服务不可用（503）。"""

    status_code = _status.HTTP_503_SERVICE_UNAVAILABLE
    default_detail = "服务暂时不可用"


class TotpRequiredException(AuthException):
    """用户已启用 TOTP，但登录请求未提供 2FA 验证码。

    全局处理器会将此异常转换为 401 响应，正文包含
    `{"detail": "...", "extra": {"code": "totp_required"}}`，
    前端据此展示 TOTP 验证码输入界面。
    """

    status_code = _status.HTTP_401_UNAUTHORIZED
    default_detail = "需要 TOTP 验证码"

    def __init__(self, detail: str | None = None) -> None:
        super().__init__(detail, extra={"code": "totp_required"})
