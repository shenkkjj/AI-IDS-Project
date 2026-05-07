import csv
import io

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from server.core.database import get_db
from server.core.security import get_current_user

router = APIRouter(prefix="/export", tags=["export"])


async def _get_user_id(request: Request, db: Session) -> int:
    cookie = request.cookies.get("access_token")
    auth = request.headers.get("Authorization")
    user = get_current_user(db, cookie, auth)
    return user.id


@router.get("/alerts", response_model=None)
async def export_alerts_csv(
    request: Request,
    limit: int = Query(default=1000, ge=1, le=10000),
    db: Session = Depends(get_db),
):
    user_id = await _get_user_id(request, db)
    from server.services import alert_service
    result = await alert_service.get_alerts(user_id, limit)
    items = result.get("items", [])

    headers = ["告警ID", "来源IP", "目标IP", "风险级别", "摘要", "载荷", "已拦截", "时间"]
    stream = io.StringIO()
    writer = csv.writer(stream)
    writer.writerow(headers)
    for item in items:
        raw = item.get("raw_alert") or {}
        llm = item.get("llm_analysis") or {}
        ts = raw.get("timestamp")
        time_str = ""
        if isinstance(ts, (int, float)) and ts > 0:
            from datetime import datetime, timezone
            time_str = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        writer.writerow([
            item.get("alert_id", ""),
            raw.get("source_ip", ""),
            raw.get("destination_ip", ""),
            llm.get("risk_level", ""),
            llm.get("summary", ""),
            raw.get("payload", ""),
            "是" if raw.get("blocked") else "否",
            time_str,
        ])
    stream.seek(0)
    return StreamingResponse(
        iter([stream.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=alerts.csv"},
    )


@router.get("/logs", response_model=None)
async def export_logs_csv(
    request: Request,
    limit: int = Query(default=1000, ge=1, le=10000),
    db: Session = Depends(get_db),
):
    user_id = await _get_user_id(request, db)
    result = db.execute(
        text("SELECT id, level, action, detail, ip_address, created_at "
             "FROM logs WHERE user_id = :uid OR user_id IS NULL "
             "ORDER BY created_at DESC LIMIT :lim"),
        {"uid": user_id, "lim": limit},
    )
    rows = result.fetchall()

    headers = ["ID", "级别", "操作", "详情", "IP地址", "时间"]
    stream = io.StringIO()
    writer = csv.writer(stream)
    writer.writerow(headers)
    for row in rows:
        writer.writerow(list(row))
    stream.seek(0)
    return StreamingResponse(
        iter([stream.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=logs.csv"},
    )
