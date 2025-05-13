import io
from typing import List

from fastapi import APIRouter, Depends, File, Header, HTTPException, UploadFile, status
from fastapi.responses import JSONResponse
from jose import jwt

from src.dependencies import get_token_service, get_screenshot_service
from src.models import ErrorResponse, ScreenshotUploadResult, TokenBlacklistReason, TokenPayload
from src.services.screenshot_service import ScreenshotService
from src.services.token_service import TokenService

router = APIRouter(prefix="/api")


async def validate_token(
        authorization: str = Header(...),
        token_service: TokenService = Depends(get_token_service),
) -> TokenPayload:
    """Validate JWT token from Authorization header."""
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header"
        )

    token = authorization.split(" ")[1]
    token_payload = token_service.validate_token(token)

    if not token_payload:
        # Check if token is blacklisted and provide specific error
        token_id = None
        try:
            # Extract token_id from JWT without validation
            payload = jwt.decode(token, options={"verify_signature": False})
            token_id = payload.get("token_id")
        except Exception:
            pass

        if token_id:
            reason = token_service.get_blacklist_reason(token_id)
            if reason == TokenBlacklistReason.ALREADY_USED:
                return JSONResponse(
                    status_code=status.HTTP_403_FORBIDDEN,
                    content=ErrorResponse(
                        message="Token has already been used",
                        detail="This upload token has already been used"
                    ).model_dump()
                )
            elif reason == TokenBlacklistReason.OTHER_PEER_UPLOADED:
                return JSONResponse(
                    status_code=status.HTTP_403_FORBIDDEN,
                    content=ErrorResponse(
                        message="Screenshots already uploaded",
                        detail="Another peer has already uploaded screenshots for this catalog ID"
                    ).model_dump()
                )

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token"
        )

    return token_payload


@router.post("/screenshot/{catalog_id}", response_model=ScreenshotUploadResult)
async def upload_screenshots(
        catalog_id: str,
        files: List[UploadFile] = File(...),
        token_payload: TokenPayload = Depends(validate_token),
        screenshot_service: ScreenshotService = Depends(get_screenshot_service)
):
    """Upload screenshots for a catalog_id."""
    # Validate catalog_id matches token
    if catalog_id != token_payload.catalog_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Catalog ID in URL does not match token"
        )

    # Process files
    screenshot_files = []
    content_types = []

    for file in files:
        # Read file content
        content = await file.read()
        screenshot_files.append(io.BytesIO(content))
        content_types.append(file.content_type)

    # Process screenshot upload
    screenshot_urls = screenshot_service.process_screenshot_upload(
        token_payload,
        screenshot_files,
        content_types
    )

    # Return result
    return ScreenshotUploadResult(
        catalog_id=catalog_id,
        screenshot_urls=screenshot_urls
    )
