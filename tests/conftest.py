import io
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from jose import jwt
from minio import Minio
from redis import Redis

import src.main
from src.models import (
    PeerWithMedia,
    ScreenshotRequest,
    ScreenshotTokenInfo,
    TokenPayload,
)
from src.services.kafka_service import KafkaService
from src.services.redis_service import RedisService
from src.services.screenshot_service import ScreenshotService
from src.services.storage_service import StorageService
from src.services.token_service import TokenService


# ====== Test Data Fixtures ======

@pytest.fixture
def test_data():
    """Central fixture providing test data constants used across tests."""
    return {
        "catalog_id": "test-catalog-123",
        "request_id": "test-request-456",
        "peer_id": "test-peer-789",
        "edge_id": "test-edge-012",
        "token_id": "test-token-345",
        "jwt_secret": "test-jwt-secret",
        "screenshot_urls": [
            "https://test-bucket.minio/screenshots/test-catalog-123/1.jpg",
            "https://test-bucket.minio/screenshots/test-catalog-123/2.jpg",
        ],
    }


@pytest.fixture
def sample_token_payload(test_data):
    """Create a sample TokenPayload for testing."""
    return TokenPayload(
        peer_id=test_data["peer_id"],
        catalog_id=test_data["catalog_id"],
        request_id=test_data["request_id"],
        token_id=test_data["token_id"],
        exp=datetime.now() + timedelta(minutes=30),
    )


@pytest.fixture
def sample_screenshot_request(test_data):
    """Create a sample ScreenshotRequest for testing."""
    return ScreenshotRequest(
        catalog_id=test_data["catalog_id"],
        request_id=test_data["request_id"],
        requester_service="test-service",
        created_at=datetime.now(),
        expires_at=datetime.now() + timedelta(hours=24),
    )


@pytest.fixture
def sample_peer_with_media(test_data):
    """Create a sample PeerWithMedia for testing."""
    return PeerWithMedia(
        peer_id=test_data["peer_id"],
        edge_id=test_data["edge_id"],
        catalog_ids=[test_data["catalog_id"], "another-catalog-id"],
    )


@pytest.fixture
def sample_token_info(test_data):
    """Create a sample ScreenshotTokenInfo for testing."""
    encoded_jwt = jwt.encode(
        {
            "peer_id": test_data["peer_id"],
            "catalog_id": test_data["catalog_id"],
            "request_id": test_data["request_id"],
            "token_id": test_data["token_id"],
            "exp": (datetime.now() + timedelta(minutes=30)).timestamp(),
        },
        test_data["jwt_secret"],
        algorithm="HS256",
    )

    return ScreenshotTokenInfo(
        token=encoded_jwt,
        peer_id=test_data["peer_id"],
        catalog_id=test_data["catalog_id"],
        request_id=test_data["request_id"],
        token_id=test_data["token_id"],
    )


@pytest.fixture
def sample_screenshot_files():
    """Create sample screenshot binary data for testing."""
    return [
        io.BytesIO(b"fake-screenshot-data-1"),
        io.BytesIO(b"fake-screenshot-data-2"),
    ]


@pytest.fixture
def sample_content_types():
    """Create sample content types for testing."""
    return ["image/jpeg", "image/jpeg"]


# ====== Mock Service Fixtures ======

@pytest.fixture
def mock_redis():
    """Mock Redis client."""
    redis_mock = MagicMock(spec=Redis)

    # Common Redis mocked behaviors
    redis_mock.hgetall.return_value = {}
    redis_mock.exists.return_value = False
    redis_mock.setex.return_value = True
    redis_mock.hset.return_value = 1
    redis_mock.hdel.return_value = 1
    redis_mock.get.return_value = None

    return redis_mock


@pytest.fixture
def mock_producer():
    """Mock Kafka Producer."""
    producer_mock = MagicMock()
    producer_mock.produce.return_value = None
    producer_mock.flush.return_value = None
    return producer_mock


@pytest.fixture
def mock_consumer():
    """Mock Kafka Consumer."""
    consumer_mock = MagicMock()
    consumer_mock.poll.return_value = None
    consumer_mock.subscribe.return_value = None
    consumer_mock.close.return_value = None
    return consumer_mock


@pytest.fixture
def mock_minio_client():
    """Mock MinIO client."""
    minio_mock = MagicMock(spec=Minio)
    minio_mock.bucket_exists.return_value = True
    minio_mock.make_bucket.return_value = None
    minio_mock.put_object.return_value = None
    minio_mock.presigned_get_object.return_value = "https://minio/presigned-url"
    return minio_mock


# ====== Service Fixtures ======

@pytest.fixture
def token_service(mock_redis, test_data):
    """Create a TokenService with controlled behavior."""
    with patch("src.services.token_service.jwt") as jwt_mock:
        jwt_mock.encode.return_value = "mocked-jwt-token"
        jwt_mock.decode.return_value = {
            "peer_id": test_data["peer_id"],
            "catalog_id": test_data["catalog_id"],
            "request_id": test_data["request_id"],
            "token_id": test_data["token_id"],
            "exp": (datetime.now() + timedelta(minutes=30)).timestamp(),
        }

        service = TokenService(mock_redis)
        # Override config for testing
        service.jwt_config.secret_key = test_data["jwt_secret"]
        service.jwt_config.algorithm = "HS256"
        service.jwt_config.token_expire_minutes = 30

        return service


@pytest.fixture
def redis_service(mock_redis):
    """Create a RedisService with mocked Redis client."""
    return RedisService(mock_redis)


@pytest.fixture
def kafka_service(mock_producer, mock_consumer):
    """Create a KafkaService with mocked Producer and Consumer."""
    with patch("src.services.kafka_service.Producer", return_value=mock_producer):
        service = KafkaService()
        service.producer = mock_producer
        service.consumer = mock_consumer
        return service


@pytest.fixture
def storage_service(mock_minio_client):
    """Create a StorageService with mocked MinIO client."""
    with patch("src.services.storage_service.Minio", return_value=mock_minio_client):
        service = StorageService()
        service.client = mock_minio_client
        return service


@pytest.fixture
def screenshot_service(token_service, redis_service, kafka_service, storage_service):
    """Create a ScreenshotService with mocked dependencies."""
    return ScreenshotService(
        token_service=token_service,
        redis_service=redis_service,
        kafka_service=kafka_service,
        storage_service=storage_service,
    )


# ====== HTTP Related Fixtures ======

@pytest.fixture
def mock_httpx_response():
    """Create a mock httpx response."""
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = []
    response.text = "{}"
    return response


@pytest.fixture
def mock_httpx_client(mock_httpx_response):
    """Create a mock httpx client with controlled behavior."""
    client = AsyncMock()
    client.__aenter__.return_value = client
    client.get.return_value = mock_httpx_response
    client.post.return_value = mock_httpx_response
    return client


@pytest.fixture
def app_with_mocked_deps():
    """Create a FastAPI app with mocked dependencies."""
    app = src.main.app

    # Store original dependencies to restore later
    original_get_redis_client = src.api.dependencies.get_redis_client
    original_get_token_service = src.api.dependencies.get_token_service
    original_get_redis_service = src.api.dependencies.get_redis_service
    original_get_kafka_service = src.api.dependencies.get_kafka_service
    original_get_storage_service = src.api.dependencies.get_storage_service
    original_get_screenshot_service = src.api.dependencies.get_screenshot_service

    # Override dependencies
    @app.dependency_overrides[src.api.dependencies.get_redis_client]
    def mock_get_redis_client():
        return MagicMock(spec=Redis)

    @app.dependency_overrides[src.api.dependencies.get_token_service]
    def mock_get_token_service():
        mock = MagicMock(spec=TokenService)
        mock.validate_token.return_value = TokenPayload(
            peer_id="test-peer-id",
            catalog_id="test-catalog-id",
            request_id="test-request-id",
            token_id="test-token-id",
            exp=datetime.now() + timedelta(minutes=30),
        )
        return mock

    @app.dependency_overrides[src.api.dependencies.get_screenshot_service]
    def mock_get_screenshot_service():
        mock = MagicMock(spec=ScreenshotService)
        mock.process_screenshot_upload.return_value = ["url1", "url2"]
        return mock

    yield app

    # Restore original dependencies
    app.dependency_overrides.clear()


@pytest.fixture
def test_client(app_with_mocked_deps):
    """Create a test client for the FastAPI app."""
    with TestClient(app_with_mocked_deps) as client:
        yield client
