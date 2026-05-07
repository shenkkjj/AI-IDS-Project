from typing import Any

from fastapi import APIRouter, Depends

from server.core.rbac import require_admin
from server.models_db import User

router = APIRouter(prefix="/threat-intel", tags=["威胁情报"])


@router.post("/refresh")
async def refresh_threat_intel(
    user: User = Depends(require_admin),
) -> dict[str, Any]:
    from server.services import threat_intel_service
    total, stats = await threat_intel_service.refresh_blacklist()
    return {"status": "refreshed", "total_ips": total, "feeds": stats}


@router.get("/check/{ip}")
async def check_ip(
    ip: str,
) -> dict[str, Any]:
    from server.services import threat_intel_service
    blacklisted = threat_intel_service.is_blacklisted(ip)
    return {"ip": ip, "blacklisted": blacklisted, "cache_size": threat_intel_service.get_blacklist_size()}


@router.get("/status")
async def threat_intel_status() -> dict[str, Any]:
    from server.services import threat_intel_service
    return {"cache_size": threat_intel_service.get_blacklist_size()}
