import json

from freezegun import freeze_time

from tests.conftest import *  # Import all fixtures


@pytest.mark.unit
class TestRedisService:
    def test_add_pending_request_with_expiration(self, redis_service, mock_redis, sample_screenshot_request):
        # Call the method
        redis_service.add_pending_request(sample_screenshot_request)

        # Verify Redis hset was called with correct parameters
        catalog_key = f"{redis_service.redis_config.pending_requests_prefix}{sample_screenshot_request.catalog_id}"
        mock_redis.hset.assert_called_once()
        args, kwargs = mock_redis.hset.call_args

        assert args[0] == catalog_key
        assert args[1] == sample_screenshot_request.request_id
        assert isinstance(args[2], str)  # JSON string

        # Verify JSON content
        request_json = json.loads(args[2])
        assert request_json["catalog_id"] == sample_screenshot_request.catalog_id
        assert request_json["request_id"] == sample_screenshot_request.request_id
        assert request_json["requester_service"] == sample_screenshot_request.requester_service

        # Verify Redis expire was called with correct TTL
        mock_redis.expire.assert_called_once()
        args, kwargs = mock_redis.expire.call_args
        assert args[0] == catalog_key
        # TTL should be positive
        assert args[1] > 0

    def test_add_pending_request_without_expiration(self, redis_service, mock_redis, sample_screenshot_request):
        # Remove expiration time to test auto-setting it
        sample_screenshot_request.expires_at = None

        # Set the created_at time to match our frozen time to avoid timing issues
        frozen_time = datetime(2025, 5, 13, 12, 0, 0)

        with freeze_time(frozen_time):
            # Set the created_at to the frozen time
            sample_screenshot_request.created_at = frozen_time

            # Call the method
            redis_service.add_pending_request(sample_screenshot_request)

            # Verify Redis expire was called with correct TTL based on service config
            mock_redis.expire.assert_called_once()
            ttl = mock_redis.expire.call_args[0][1]
            expected_ttl = redis_service.service_config.pending_request_ttl_hours * 3600

            # Allow small difference due to execution time
            assert abs(ttl - expected_ttl) < 10

    def test_add_pending_request_expired(self, redis_service, mock_redis, sample_screenshot_request):
        # Set expiration time in the past
        sample_screenshot_request.expires_at = datetime.now() - timedelta(hours=1)

        # Call the method
        redis_service.add_pending_request(sample_screenshot_request)

        # Verify Redis hset and expire were not called
        mock_redis.hset.assert_not_called()
        mock_redis.expire.assert_not_called()

    def test_get_pending_requests_empty(self, redis_service, mock_redis, test_data):
        # Setup Redis to return empty hash
        mock_redis.hgetall.return_value = {}

        # Call the method
        result = redis_service.get_pending_requests(test_data["catalog_id"])

        # Verify Redis hgetall was called with correct key
        catalog_key = f"{redis_service.redis_config.pending_requests_prefix}{test_data['catalog_id']}"
        mock_redis.hgetall.assert_called_once_with(catalog_key)

        # Verify result
        assert result == []

    def test_get_pending_requests_with_data(self, redis_service, mock_redis, test_data, sample_screenshot_request):
        # Setup Redis to return a hash with a request
        request_json = sample_screenshot_request.model_dump_json()
        mock_redis.hgetall.return_value = {
            sample_screenshot_request.request_id.encode("utf-8"): request_json.encode("utf-8")
        }

        # Call the method
        result = redis_service.get_pending_requests(test_data["catalog_id"])

        # Verify Redis hgetall was called with correct key
        catalog_key = f"{redis_service.redis_config.pending_requests_prefix}{test_data['catalog_id']}"
        mock_redis.hgetall.assert_called_once_with(catalog_key)

        # Verify result
        assert len(result) == 1
        assert isinstance(result[0], ScreenshotRequest)
        assert result[0].catalog_id == sample_screenshot_request.catalog_id
        assert result[0].request_id == sample_screenshot_request.request_id
        assert result[0].requester_service == sample_screenshot_request.requester_service

    def test_remove_pending_request(self, redis_service, mock_redis, test_data):
        catalog_id = test_data["catalog_id"]
        request_id = test_data["request_id"]

        # Call the method
        redis_service.remove_pending_request(catalog_id, request_id)

        # Verify Redis hdel was called with correct parameters
        catalog_key = f"{redis_service.redis_config.pending_requests_prefix}{catalog_id}"
        mock_redis.hdel.assert_called_once_with(catalog_key, request_id)

    def test_get_all_pending_catalog_ids(self, redis_service, mock_redis):
        # Setup Redis to return keys
        prefix = redis_service.redis_config.pending_requests_prefix
        mock_redis.keys.return_value = [
            f"{prefix}catalog-1".encode("utf-8"),
            f"{prefix}catalog-2".encode("utf-8"),
        ]

        # Call the method
        result = redis_service.get_all_pending_catalog_ids()

        # Verify Redis keys was called with correct pattern
        mock_redis.keys.assert_called_once_with(f"{prefix}*")

        # Verify result
        assert result == {"catalog-1", "catalog-2"}
