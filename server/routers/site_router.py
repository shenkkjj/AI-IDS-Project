from typing import Any

from fastapi import APIRouter, Cookie, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from server.core.database import get_db
from server.core.security import get_current_user
from server.models.schemas import SiteTargetIn
from server.services.site_monitor_service import set_site_target, get_site_health

router = APIRouter(prefix="/site", tags=["站点监控"])


@router.post("/target")
async def post_site_target(
    data: SiteTargetIn,
    authorization: str | None = Header(default=None, alias="Authorization"),
    access_token_cookie: str | None = Cookie(default=None, alias="access_token"),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    user = get_current_user(db, access_token_cookie, authorization)
    try:
        return await set_site_target(user.id, data.url, db)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.get("/health")
async def get_site_health_route(
    authorization: str | None = Header(default=None, alias="Authorization"),
    access_token_cookie: str | None = Cookie(default=None, alias="access_token"),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    user = get_current_user(db, access_token_cookie, authorization)
    return get_site_health(user.id)
