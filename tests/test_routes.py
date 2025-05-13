from fastapi import HTTPException, status, FastAPI

from src.api.routes import router, validate_token
from src.main import app
from tests.conftest import *  # Import all fixtures


@pytest.fixture
def app_with_routes():
    """Create FastAPI app with routes for testing."""
    test_app = FastAPI()
    test_app.include_router(router)
    return test_app


@pytest.fixture
def route_test_client(app_with_routes):
    """Create test client for routes."""
    return TestClient(app_with_routes)


@pytest.mark.unit
class TestRoutes:
    @pytest.mark.asyncio
    async def test_validate_token_valid(self):
        # Setup token_service mock
        token_service = MagicMock()
        sample_token_payload = MagicMock(spec=TokenPayload)
        token_service.validate_token.return_value = sample_token_payload

        # Call the function
        result = await validate_token("Bearer valid-token", token_service)

        # Verify token_service.validate_token was called
        token_service.validate_token.assert_called_once_with("valid-token")

        # Verify result
        assert result == sample_token_payload

    @pytest.mark.asyncio
    async def test_validate_token_invalid_header(self):
        # Setup token_service mock
        token_service = MagicMock()

        # Call the function with invalid header
        with pytest.raises(HTTPException) as excinfo:
            await validate_token("Invalid", token_service)

        # Verify exception details
        assert excinfo.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Invalid authorization header" in excinfo.value.detail

        # Verify token_service.validate_token was not called
        token_service.validate_token.assert_not_called()

    @pytest.mark.asyncio
    async def test_validate_token_invalid_token(self):
        # Setup token_service mock
        token_service = MagicMock()
        token_service.validate_token.return_value = None
        token_service.get_blacklist_reason.return_value = None

        # Mock jwt.decode to return a token_id
        with patch("src.api.routes.jwt.decode") as jwt_decode_mock:
            jwt_decode_mock.return_value = {"token_id": "test-token-id"}

            # Call the function
            with pytest.raises(HTTPException) as excinfo:
                await validate_token("Bearer invalid-token", token_service)

            # Verify exception details
            assert excinfo.value.status_code == status.HTTP_401_UNAUTHORIZED
            assert "Invalid or expired token" in excinfo.value.detail

            # Verify token_service.validate_token was called
            token_service.validate_token.assert_called_once_with("invalid-token")

            # Verify token_service.get_blacklist_reason was called
            token_service.get_blacklist_reason.assert_called_once_with("test-token-id")


@pytest.mark.skip
@pytest.mark.integration
class TestIntegrationRoutes:
    def test_upload_screenshots_integration(self, test_client, test_data, token_service, screenshot_service):
        """Test upload_screenshots endpoint with mocked dependencies."""
        # Create a valid token
        token_info = token_service.create_token(
            test_data["peer_id"],
            test_data["catalog_id"],
            test_data["request_id"]
        )

        # Set up screenshot_service to process upload
        screenshot_urls = [f"https://minio/{test_data['catalog_id']}/1.jpg"]
        screenshot_service.process_screenshot_upload.return_value = screenshot_urls

        # Call the endpoint
        files = [
            ("files", ("screenshot1.jpg", b"test-data", "image/jpeg")),
        ]

        headers = {"Authorization": f"Bearer {token_info.token}"}

        response = test_client.post(f"/api/screenshot/{test_data['catalog_id']}", files=files, headers=headers)

        # Verify response
        assert response.status_code == 200

        # Verify response JSON
        response_json = response.json()
        assert response_json["catalog_id"] == test_data["catalog_id"]
        assert response_json["screenshot_urls"] == screenshot_urls
        assert response_json["status"] == "success"

        # Verify screenshot_service.process_screenshot_upload was called
        screenshot_service.process_screenshot_upload.assert_called_once()


@pytest.mark.skip
class TestMainApp:
    def test_global_exception_handler(self, test_client):
        """Test global exception handler."""

        # Mock a route that raises an exception
        @app.get("/test/exception")
        async def raise_exception():
            raise Exception("Test exception")

        # Call the endpoint
        response = test_client.get("/test/exception")

        # Verify response
        assert response.status_code == 500
        assert response.json()["status"] == "error"
        assert response.json()["message"] == "Internal server error"
        assert "Test exception" in response.json()["detail"]
