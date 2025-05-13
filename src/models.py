from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class TokenBlacklistReason(str, Enum):
    ALREADY_USED = "already_used"
    OTHER_PEER_UPLOADED = "other_peer_uploaded"
    EXPIRED = "expired"


class ScreenshotRequest(BaseModel):
    catalog_id: str
    request_id: str
    requester_service: str
    created_at: datetime = Field(default_factory=datetime.now)
    expires_at: Optional[datetime] = None


class TokenPayload(BaseModel):
    peer_id: str
    catalog_id: str
    request_id: str
    token_id: str
    exp: datetime


class ScreenshotTokenInfo(BaseModel):
    token: str
    peer_id: str
    catalog_id: str
    request_id: str
    token_id: str


class PeerWithMedia(BaseModel):
    peer_id: str
    edge_id: str
    catalog_ids: List[str]


class ScreenshotUploadResult(BaseModel):
    catalog_id: str
    screenshot_urls: List[str]
    status: str = "success"
    message: str = "Screenshots uploaded successfully"


class ErrorResponse(BaseModel):
    status: str = "error"
    message: str
    detail: Optional[str] = None
