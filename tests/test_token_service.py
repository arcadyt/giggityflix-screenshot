import uuid

from freezegun import freeze_time

from src.models import TokenBlacklistReason
from tests.conftest import *  # Import all fixtures


@pytest.mark.unit
class TestTokenService:
    def test_create_token(self, token_service, test_data):
        peer_id = test_data["peer_id"]
        catalog_id = test_data["catalog_id"]
        request_id = test_data["request_id"]
        token_id = test_data["token_id"]

        # Use a mock for uuid4 instead of trying to create a real UUID
        mock_uuid = MagicMock()
        mock_uuid.hex = token_id
        mock_uuid.__str__.return_value = token_id

        # Explicitly patch jwt.encode to return "mocked-jwt-token"
        with patch("src.services.token_service.jwt.encode", return_value="mocked-jwt-token"):
            with patch("uuid.uuid4", return_value=mock_uuid):
                with freeze_time("2025-05-13 12:00:00"):
                    token_info = token_service.create_token(peer_id, catalog_id, request_id)

                    assert token_info.peer_id == peer_id
                    assert token_info.catalog_id == catalog_id
                    assert token_info.request_id == request_id
                    assert token_info.token_id == token_id
                    assert token_info.token == "mocked-jwt-token"

                    # Verify jwt.encode was called with correct parameters
                    # We need to use the patched version from the context
                    from src.services.token_service import jwt as patched_jwt
                    patched_jwt.encode.assert_called_once()
                    args, kwargs = patched_jwt.encode.call_args

                    payload = args[0]
                    assert payload["peer_id"] == peer_id
                    assert payload["catalog_id"] == catalog_id
                    assert payload["request_id"] == request_id
                    assert payload["token_id"] == token_id
                    assert "exp" in payload

                    assert kwargs["algorithm"] == "HS256"

    def test_validate_token_valid(self, token_service, mock_redis, test_data, sample_token_payload):
        # Setup mock Redis to indicate token is not blacklisted
        mock_redis.exists.return_value = False

        # We need to ensure jwt.decode returns a correctly formatted payload
        # Let's patch it directly inside this test
        with patch.object(jwt, 'decode', return_value={
            "peer_id": sample_token_payload.peer_id,
            "catalog_id": sample_token_payload.catalog_id,
            "request_id": sample_token_payload.request_id,
            "token_id": sample_token_payload.token_id,
            "exp": sample_token_payload.exp.timestamp()
        }):
            result = token_service.validate_token("valid-token")

            # Verify token validation
            assert result is not None
            assert result.peer_id == sample_token_payload.peer_id
            assert result.catalog_id == sample_token_payload.catalog_id
            assert result.request_id == sample_token_payload.request_id
            assert result.token_id == sample_token_payload.token_id

            # Verify Redis check
            redis_key = f"{token_service.redis_config.token_blacklist_prefix}{sample_token_payload.token_id}"
            mock_redis.exists.assert_called_once_with(redis_key)

    def test_validate_token_blacklisted(self, token_service, mock_redis, test_data):
        # Setup mock Redis to indicate token is blacklisted
        mock_redis.exists.return_value = True

        # Mock jwt.decode to return a valid payload so we reach the Redis check
        with patch.object(jwt, 'decode', return_value={
            "peer_id": test_data["peer_id"],
            "catalog_id": test_data["catalog_id"],
            "request_id": test_data["request_id"],
            "token_id": test_data["token_id"],
            "exp": (datetime.now() + timedelta(minutes=30)).timestamp()
        }):
            result = token_service.validate_token("blacklisted-token")

            # Verify token validation fails
            assert result is None

            # Verify Redis check
            redis_key = f"{token_service.redis_config.token_blacklist_prefix}{test_data['token_id']}"
            mock_redis.exists.assert_called_once_with(redis_key)

    def test_validate_token_invalid(self, token_service):
        # Setup JWT to raise an exception
        with patch("src.services.token_service.jwt.decode", side_effect=jwt.JWTError("Invalid token")):
            result = token_service.validate_token("invalid-token")

            # Verify token validation fails
            assert result is None

    def test_blacklist_token(self, token_service, mock_redis, test_data):
        token_id = test_data["token_id"]
        reason = TokenBlacklistReason.ALREADY_USED
        ttl_hours = 24

        token_service.blacklist_token(token_id, reason, ttl_hours)

        # Verify Redis setex was called with correct parameters
        blacklist_key = f"{token_service.redis_config.token_blacklist_prefix}{token_id}"
        mock_redis.setex.assert_called_once()
        args, kwargs = mock_redis.setex.call_args

        assert args[0] == blacklist_key
        assert isinstance(args[1], timedelta)
        assert args[1].total_seconds() == ttl_hours * 3600
        assert args[2] == reason.value

    def test_get_blacklist_reason_exists(self, token_service, mock_redis, test_data):
        token_id = test_data["token_id"]
        reason = TokenBlacklistReason.ALREADY_USED

        # Setup Redis to return a reason
        mock_redis.get.return_value = reason.value.encode("utf-8")

        result = token_service.get_blacklist_reason(token_id)

        # Verify Redis get was called with correct key
        blacklist_key = f"{token_service.redis_config.token_blacklist_prefix}{token_id}"
        mock_redis.get.assert_called_once_with(blacklist_key)

        # Verify result
        assert result == reason

    def test_get_blacklist_reason_not_exists(self, token_service, mock_redis, test_data):
        token_id = test_data["token_id"]

        # Setup Redis to return None
        mock_redis.get.return_value = None

        result = token_service.get_blacklist_reason(token_id)

        # Verify Redis get was called with correct key
        blacklist_key = f"{token_service.redis_config.token_blacklist_prefix}{token_id}"
        mock_redis.get.assert_called_once_with(blacklist_key)

        # Verify result
        assert result is None