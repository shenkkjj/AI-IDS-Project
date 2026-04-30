import asyncio
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any

from server.core.config import ALERT_BACKLOG_SIZE, ALERT_EMAIL_COOLDOWN_SECONDS, ALERT_QUEUE_MAX_SIZE
from server.models.schemas import AlertIn


@dataclass
class SiteMonitorState:
    targets: dict[int, str] = field(default_factory=dict)
    health_status: dict[int, dict[str, Any]] = field(default_factory=dict)


@dataclass
class AlertState:
    backlog: deque[dict[str, Any]] = field(default_factory=lambda: deque(maxlen=ALERT_BACKLOG_SIZE))
    email_last_sent: dict[int, float] = field(default_factory=dict)
    queue: asyncio.Queue[AlertIn] = field(default_factory=lambda: asyncio.Queue(maxsize=ALERT_QUEUE_MAX_SIZE))
    backlog_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    email_lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    async def append_backlog(self, payload: dict[str, Any]) -> None:
        async with self.backlog_lock:
            self.backlog.append(payload)

    async def get_backlog_snapshot(self) -> list[dict[str, Any]]:
        async with self.backlog_lock:
            return list(self.backlog)

    def enqueue_alert(self, alert: AlertIn) -> tuple[bool, bool]:
        try:
            self.queue.put_nowait(alert)
            return True, False
        except asyncio.QueueFull:
            try:
                self.queue.get_nowait()
                self.queue.task_done()
            except asyncio.QueueEmpty:
                return False, False

            try:
                self.queue.put_nowait(alert)
                return True, True
            except asyncio.QueueFull:
                return False, True

    async def should_send_email(self, user_id: int) -> bool:
        async with self.email_lock:
            last_sent = self.email_last_sent.get(user_id, 0)
            if time.time() - last_sent < ALERT_EMAIL_COOLDOWN_SECONDS:
                return False
            self.email_last_sent[user_id] = time.time()
            return True


@dataclass
class RateLimitState:
    login_attempts: dict[str, list[float]] = field(default_factory=dict)
    register_attempts: dict[str, list[float]] = field(default_factory=dict)
    otp_attempts: dict[str, list[float]] = field(default_factory=dict)
    copilot_attempts: dict[str, list[float]] = field(default_factory=dict)
    llm_attempts: dict[str, list[float]] = field(default_factory=dict)
    login_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    otp_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    register_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    llm_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    copilot_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    otp_verify_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    otp_verify_failures: dict[str, int] = field(default_factory=dict)

    def _check_rate_limit(self, attempts: dict[str, list[float]], key: str, window: int, max_attempts: int) -> bool:
        now = time.time()
        if key in attempts:
            attempts[key] = [t for t in attempts[key] if now - t < window]
        if key not in attempts or len(attempts[key]) < max_attempts:
            if key not in attempts:
                attempts[key] = []
            attempts[key].append(now)
            return True
        return False

    async def check_login_limit(self, email: str) -> bool:
        from server.core.config import LOGIN_RATE_LIMIT_WINDOW, LOGIN_RATE_LIMIT_MAX
        async with self.login_lock:
            return self._check_rate_limit(self.login_attempts, email.lower(), LOGIN_RATE_LIMIT_WINDOW, LOGIN_RATE_LIMIT_MAX)

    async def check_register_limit(self, ip: str) -> bool:
        from server.core.config import REGISTER_RATE_LIMIT_WINDOW, REGISTER_RATE_LIMIT_MAX
        async with self.register_lock:
            return self._check_rate_limit(self.register_attempts, ip, REGISTER_RATE_LIMIT_WINDOW, REGISTER_RATE_LIMIT_MAX)

    async def check_otp_limit(self, email: str) -> bool:
        from server.core.config import OTP_RATE_LIMIT_WINDOW, OTP_RATE_LIMIT_MAX
        async with self.otp_lock:
            return self._check_rate_limit(self.otp_attempts, email.lower(), OTP_RATE_LIMIT_WINDOW, OTP_RATE_LIMIT_MAX)

    async def check_copilot_limit(self, ip: str) -> bool:
        from server.core.config import COPILOT_RATE_LIMIT_WINDOW, COPILOT_RATE_LIMIT_MAX
        async with self.copilot_lock:
            return self._check_rate_limit(self.copilot_attempts, ip, COPILOT_RATE_LIMIT_WINDOW, COPILOT_RATE_LIMIT_MAX)

    async def check_llm_limit(self, ip: str) -> bool:
        from server.core.config import LLM_RATE_LIMIT_WINDOW, LLM_RATE_LIMIT_MAX
        async with self.llm_lock:
            return self._check_rate_limit(self.llm_attempts, ip, LLM_RATE_LIMIT_WINDOW, LLM_RATE_LIMIT_MAX)


@dataclass
class AppState:
    site_monitor: SiteMonitorState = field(default_factory=SiteMonitorState)
    alert: AlertState = field(default_factory=AlertState)
    rate_limit: RateLimitState = field(default_factory=RateLimitState)
    worker_tasks: list[asyncio.Task[None]] = field(default_factory=list)
    ssl_monitor_task: asyncio.Task[None] | None = None


app_state = AppState()
