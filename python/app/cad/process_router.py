"""Process router for CAD-related process management."""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter

from app.core.response import success

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/process", tags=["Process"])


@router.get("/info")
async def get_process_info() -> dict[str, Any]:
    """Get process information."""
    return success(data={"status": "active"})
