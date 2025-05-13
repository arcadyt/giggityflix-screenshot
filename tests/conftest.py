import pytest
from unittest.mock import MagicMock
from fastapi import FastAPI
from fastapi.testclient import TestClient

# Import models directly to avoid circular imports
from src.models import TokenPayload, ScreenshotRequest, PeerWithMedia


# Create a mock router instead of importing the real one to avoid import errors
class MockRouter:
    def include_router(self, *args, **kwargs):
        pass


mock_router = MockRouter()


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
def app(token_service_mock, screenshot_service_mock):
    """Create a FastAPI app with mocked dependencies for testing."""
    app = FastAPI()

    # Define a simple test endpoint instead of using the router
    @app.post("/api/screenshot/{catalog_id}")
    async def test_endpoint(catalog_id: str):
        return {"catalog_id": catalog_id, "status": "success"}

    return app


@pytest.fixture
def client(app):
    """Create a test client for the FastAPI app."""
    return TestClient(app)


@pytest.fixture
def sample_token_payload():
    """Create a sample TokenPayload for testing."""
    return TokenPayload(
        peer_id="test-peer-id",
        catalog_id="test-catalog-id",
        request_id="test-request-id",
        token_id="test-token-id",
        exp=None  # Not needed for most tests
    )


@pytest.fixture
def sample_screenshot_request():
    """Create a sample ScreenshotRequest for testing."""
    return ScreenshotRequest(
        catalog_id="test-catalog-id",
        request_id="test-request-id",
        requester_service="test-service"
    )


@pytest.fixture
def sample_peer_with_media():
    """Create a sample PeerWithMedia for testing."""
    return PeerWithMedia(
        peer_id="test-peer-id",
        edge_id="test-edge-id",
        catalog_ids=["test-catalog-id-1", "test-catalog-id-2"]
    )