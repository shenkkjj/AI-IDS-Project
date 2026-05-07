from typing import Any

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from server.core.database import get_db
from server.core.security import require_auth_user, require_llm_admin_token
from server.models.schemas import LLMConfigIn
from server.models_db import User
from server.services import llm_service

router = APIRouter(prefix="/llm", tags=["LLM配置"])


@router.get("/config")
async def get_llm_config(
    _: None = Depends(require_llm_admin_token),
) -> dict[str, Any]:
    config = await llm_service.get_runtime_llm_config()
    from server.core.llm_utils import choose_provider
    provider = choose_provider("custom", config.model, config.base_url)
    from server.core.llm_utils import config_to_payload
    return config_to_payload(config, provider)


@router.put("/config")
async def put_llm_config(
    data: LLMConfigIn,
    _: None = Depends(require_llm_admin_token),
) -> dict[str, Any]:
    config = await llm_service.update_runtime_llm_config(data)
    from server.core.llm_utils import choose_provider, config_to_payload
    provider = choose_provider(data.ai_provider, config.model, config.base_url)
    return {"status": "updated", "config": config_to_payload(config, provider)}


@router.post("/test")
async def post_llm_test(
    data: LLMConfigIn,
    request: Request,
    user: User = Depends(require_auth_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return await llm_service.test_llm_config(data, user, request, db)
