import json
from datetime import datetime, timedelta
from typing import List, Set

from redis import Redis

from src.config import config
from src.models import ScreenshotRequest


class RedisService:
    def __init__(self, redis_client: Redis):
        self.redis_client = redis_client
        self.redis_config = config.redis
        self.service_config = config.service

    def add_pending_request(self, request: ScreenshotRequest) -> None:
        """Add a pending screenshot request."""
        # Set expiration time if not already set
        if not request.expires_at:
            request.expires_at = request.created_at + timedelta(
                hours=self.service_config.pending_request_ttl_hours
            )

        # Create Redis key
        catalog_key = f"{self.redis_config.pending_requests_prefix}{request.catalog_id}"

        # Serialize request to JSON
        request_json = request.model_dump_json()

        # Store in Redis with expiration
        ttl_seconds = int((request.expires_at - datetime.now()).total_seconds())
        if ttl_seconds > 0:
            self.redis_client.hset(catalog_key, request.request_id, request_json)
            self.redis_client.expire(catalog_key, ttl_seconds)

    def get_pending_requests(self, catalog_id: str) -> List[ScreenshotRequest]:
        """Get all pending requests for a catalog_id."""
        catalog_key = f"{self.redis_config.pending_requests_prefix}{catalog_id}"

        # Get all requests from Redis hash
        requests_json = self.redis_client.hgetall(catalog_key)

        # Parse requests
        requests = []
        for request_json in requests_json.values():
            request_dict = json.loads(request_json)
            # Convert string dates back to datetime objects
            if isinstance(request_dict["created_at"], str):
                request_dict["created_at"] = datetime.fromisoformat(request_dict["created_at"])
            if request_dict.get("expires_at") and isinstance(request_dict["expires_at"], str):
                request_dict["expires_at"] = datetime.fromisoformat(request_dict["expires_at"])

            requests.append(ScreenshotRequest(**request_dict))

        return requests

    def remove_pending_request(self, catalog_id: str, request_id: str) -> None:
        """Remove a pending request."""
        catalog_key = f"{self.redis_config.pending_requests_prefix}{catalog_id}"
        self.redis_client.hdel(catalog_key, request_id)

    def get_all_pending_catalog_ids(self) -> Set[str]:
        """Get all catalog_ids with pending requests."""
        # Get all keys matching the prefix
        keys = self.redis_client.keys(f"{self.redis_config.pending_requests_prefix}*")

        # Extract catalog_ids from keys
        catalog_ids = set()
        prefix_len = len(self.redis_config.pending_requests_prefix)
        for key in keys:
            catalog_id = key.decode('utf-8')[prefix_len:]
            catalog_ids.add(catalog_id)

        return catalog_ids
