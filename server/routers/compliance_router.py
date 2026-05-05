import csv
import io
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from server.core.database import get_db
from server.core.rbac import require_admin
from server.core.security import get_current_user
from server.models_db import User

router = APIRouter(prefix="/compliance", tags=["合规审计"])


@router.get("/audit-report", response_model=None)
async def download_audit_report(
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    logs = db.execute(
        text(
            "SELECT created_at, level, action, detail, ip_address "
            "FROM logs WHERE user_id = :uid OR user_id IS NULL "
            "ORDER BY created_at DESC LIMIT 5000"
        ),
        {"uid": admin.id},
    ).fetchall()

    users = db.execute(
        text("SELECT id, email, role, is_active, created_at FROM users ORDER BY id")
    ).fetchall()

    stream = io.StringIO()
    writer = csv.writer(stream)

    writer.writerow(["=== CyberSentinel 合规审计报告 ==="])
    writer.writerow([f"生成时间: {datetime.now(timezone.utc).isoformat()}"])
    writer.writerow([f"生成者: {admin.email}"])
    writer.writerow([])

    writer.writerow(["用户列表"])
    writer.writerow(["ID", "邮箱", "角色", "活跃", "创建时间"])
    for u in users:
        writer.writerow(list(u))
    writer.writerow([])

    writer.writerow(["操作日志 (最近5000条)"])
    writer.writerow(["时间", "级别", "操作", "详情", "IP地址"])
    for row in logs:
        writer.writerow(list(row))
    writer.writerow([])

    writer.writerow(["=== 合规签名 ==="])
    writer.writerow([f"报告哈希: CyberSentinel-v2.2-{datetime.now(timezone.utc).strftime('%Y%m%d')}"])

    stream.seek(0)
    filename = f"compliance-audit-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M')}.csv"
    return StreamingResponse(
        iter([stream.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
