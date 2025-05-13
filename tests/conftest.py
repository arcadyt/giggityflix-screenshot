import pytest
import sys
from pathlib import Path
from unittest.mock import MagicMock

# Add tests directory to Python path first, so our test config is found
tests_path = Path(__file__).parent
sys.path.insert(0, str(tests_path))

# Then add src directory to Python path
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

# Now imports from src will find the config module in the tests directory
from models import TokenPayload, ScreenshotRequest, PeerWithMedia


@pytest.fixture
def token_service_mock():
    """Create a mock TokenService for testing."""
    mock = MagicMock()
    return mock


@pytest.fixture
def redis_service_mock():
    """Create a mock RedisService for testing."""
    mock = MagicMock()
    return mock


@pytest.fixture
def kafka_service_mock():
    """Create a mock KafkaService for testing."""
    mock = MagicMock()
    return mock


@pytest.fixture
def storage_service_mock():
    """Create a mock StorageService for testing."""
    mock = MagicMock()
    return mock


@pytest.fixture
def screenshot_service_mock(
        token_service_mock, redis_service_mock, kafka_service_mock, storage_service_mock
):
    """Create a mock ScreenshotService for testing."""
    mock = MagicMock()
    return mock


@pytest.fixture
def app():
    """Create a FastAPI app with mocked dependencies for testing."""
    from fastapi import FastAPI
    app = FastAPI()

    # Define a simple test endpoint instead of using the router
    @app.post("/api/test")
    async def test_endpoint():
        return {"status": "success"}

    return app


@pytest.fixture
def client(app):
    """Create a test client for the FastAPI app."""
    from fastapi.testclient import TestClient
    return TestClient(app)


@pytest.fixture
def sample_token_payload():
    """Create a sample TokenPayload for testing."""
    from datetime import datetime
    return TokenPayload(
        peer_id="test-peer-id",
        catalog_id="test-catalog-id",
        request_id="test-request-id",
        token_id="test-token-id",
        exp=datetime.now()
    )


@pytest.fixture
def sample_screenshot_request():
    """Create a sample ScreenshotRequest for testing."""
    from datetime import datetime
    return ScreenshotRequest(
        catalog_id="test-catalog-id",
        request_id="test-request-id",
        requester_service="test-service",
        created_at=datetime.now()
    )


@pytest.fixture
def sample_peer_with_media():
    """Create a sample PeerWithMedia for testing."""
    return PeerWithMedia(
        peer_id="test-peer-id",
        edge_id="test-edge-id",
        catalog_ids=["test-catalog-id-1", "test-catalog-id-2"]
    )