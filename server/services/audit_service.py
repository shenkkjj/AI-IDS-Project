from sqlalchemy.orm import Session

from server.models_db import AuditLog


class AuditAction:
    LOGIN_SUCCESS = "login_success"
    LOGIN_FAILED = "login_failed"
    LOGOUT = "logout"
    REGISTER = "register"
    PASSWORD_CHANGE = "password_change"
    TOTP_ENABLE = "totp_enable"
    TOTP_DISABLE = "totp_disable"
    TOTP_VERIFY = "totp_verify"
    API_KEY_SET = "api_key_set"
    API_KEY_DELETE = "api_key_delete"
    CONFIG_CHANGE = "config_change"
    ROLE_CHANGE = "role_change"
    USER_DELETE = "user_delete"
    ALERT_CONFIRM = "alert_confirm"
    THREAT_BLOCK = "threat_block"


def create_audit_log(
    db: Session,
    action: str,
    user_id: int | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
    detail: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    status: str = "success",
) -> AuditLog:
    audit = AuditLog(
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        detail=detail,
        ip_address=ip_address,
        user_agent=user_agent,
        status=status,
    )
    db.add(audit)
    db.commit()
    return audit


def get_audit_logs(
    db: Session,
    user_id: int | None = None,
    action: str | None = None,
    limit: int = 100,
) -> list[AuditLog]:
    query = db.query(AuditLog)
    if user_id is not None:
        query = query.filter(AuditLog.user_id == user_id)
    if action is not None:
        query = query.filter(AuditLog.action == action)
    return query.order_by(AuditLog.created_at.desc()).limit(limit).all()
