import asyncio
import logging
import os
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from src.api.routes import router
from src.dependencies import get_kafka_service, get_screenshot_service
from src.models import ErrorResponse

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle events"""
    # Startup logic
    logger.info("Starting Screenshot Service...")

    # Get service instances
    kafka_service = get_kafka_service()
    screenshot_service = get_screenshot_service()

    # Create handler functions that don't return anything
    def handle_screenshot_request(request: Any) -> None:
        asyncio.create_task(screenshot_service.handle_screenshot_request(request))

    def handle_peer_available(peer: Any) -> None:
        asyncio.create_task(screenshot_service.handle_peer_available(peer))

    # Start Kafka consumer with proper function signature
    kafka_service.start_consuming(
        screenshots_requested_handler=handle_screenshot_request,
        peer_available_handler=handle_peer_available
    )

    logger.info("Screenshot Service started successfully")

    yield  # Service runs here

    # Shutdown logic
    logger.info("Shutting down Screenshot Service...")
    kafka_service.stop_consuming()
    logger.info("Screenshot Service shutdown complete")


# Create FastAPI app with lifespan
app = FastAPI(
    title="Screenshot Service",
    description="Service for handling screenshot requests and uploads",
    version="1.0.0",
    lifespan=lifespan
)

# Include API routes
app.include_router(router)


# Handle exceptions
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler for unhandled exceptions"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=ErrorResponse(
            message="Internal server error",
            detail=str(exc)
        ).model_dump()
    )


# Run application
if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", "8000"))

    uvicorn.run(
        "src.main:app",  # Adjust this path based on where main.py is located
        host="0.0.0.0",
        port=port,
        reload=True  # Set to False in production
    )
