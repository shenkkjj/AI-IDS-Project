from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from server.core.database import get_db
from server.core.rbac import Role, require_admin
from server.models_db import User

router = APIRouter(prefix="/admin/roles", tags=["角色管理"])


@router.get("/users")
async def list_users(
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> list[dict[str, Any]]:
    from server.models_db import User as UserModel
    users = db.query(UserModel).order_by(UserModel.id).all()
    return [
        {
            "id": u.id,
            "email": u.email,
            "role": u.role,
            "display_name": u.display_name,
            "is_active": u.is_active,
        }
        for u in users
    ]


@router.patch("/users/{user_id}")
async def update_user_role(
    user_id: int,
    role: str = "analyst",
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
) -> dict[str, Any]:
    allowed = {r.value for r in Role}
    if role not in allowed:
        raise HTTPException(status_code=400, detail=f"无效角色: {role}，允许: {allowed}")

    from server.models_db import User as UserModel
    target = db.query(UserModel).filter(UserModel.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="用户不存在")
    if target.id == admin.id:
        raise HTTPException(status_code=400, detail="不能修改自己的角色")

    target.role = role
    db.commit()
    return {"status": "ok", "user_id": user_id, "role": role}
