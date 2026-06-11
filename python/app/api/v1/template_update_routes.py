"""Template Update Service API Routes."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.templates.template_update_service import get_update_service
from app.core.response import success, error

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/templates/updates", tags=["updates"])


class CreateNotificationRequest(BaseModel):
    project_id: str = Field(..., description="Project ID")
    suggestion: Dict[str, Any] = Field(..., description="Suggestion data")
    priority: str = Field(
        default="optional", description="Priority: optional/recommended/critical"
    )


class ScanUpdatesRequest(BaseModel):
    project_id: str = Field(..., description="Project ID")
    suggestions: List[Dict[str, Any]] = Field(
        ..., description="List of suggestions to check"
    )


@router.get("/{project_id}")
def get_notifications(
    project_id: str,
    status: Optional[str] = None,
):
    """Get update notifications for a project."""
    service = get_update_service()
    notifs = service.get_notifications(project_id, status_filter=status)
    return success(data=[n.to_dict() for n in notifs])


@router.post("/scan")
def scan_for_updates(req: ScanUpdatesRequest):
    """Scan for applicable updates for a project."""
    service = get_update_service()
    notifications = service.scan_for_updates(req.project_id, req.suggestions)
    return success(
        data={
            "new_notifications": len(notifications),
            "notifications": [n.to_dict() for n in notifications],
        }
    )


@router.post("/apply/{notification_id}")
def apply_update(notification_id: str):
    """Apply an update notification."""
    service = get_update_service()
    result = service.apply_update(notification_id)
    if result is None:
        return error(code="NOTIFICATION_NOT_FOUND", message="Notification not found")
    return success(data=result.to_dict())


@router.post("/dismiss/{notification_id}")
def dismiss_notification(notification_id: str):
    """Dismiss an update notification."""
    service = get_update_service()
    result = service.dismiss_notification(notification_id)
    if not result:
        return error(code="NOTIFICATION_NOT_FOUND", message="Notification not found")
    return success(data={"dismissed": True})


@router.get("/preview/{notification_id}")
def preview_update(notification_id: str):
    """Preview an update notification."""
    service = get_update_service()
    result = service.preview_update(notification_id)
    if result is None:
        return error(code="NOTIFICATION_NOT_FOUND", message="Notification not found")
    return success(data=result)
