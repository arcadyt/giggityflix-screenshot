from fastapi import Depends
from redis import Redis

from config import config
from services.token_service import TokenService
from services.redis_service import RedisService
from services.kafka_service import KafkaService
from services.storage_service import StorageService
from services.screenshot_service import ScreenshotService

def get_redis_client() -> Redis:
    """Get Redis client."""
    redis_config = config.redis
    return Redis(
        host=redis_config.host,
        port=redis_config.port,
        db=redis_config.db,
        password=redis_config.password,
        decode_responses=False  # We want bytes for token blacklist
    )

def get_token_service(redis_client: Redis = Depends(get_redis_client)) -> TokenService:
    """Get TokenService instance."""
    return TokenService(redis_client)

def get_redis_service(redis_client: Redis = Depends(get_redis_client)) -> RedisService:
    """Get RedisService instance."""
    return RedisService(redis_client)

def get_kafka_service() -> KafkaService:
    """Get KafkaService instance."""
    return KafkaService()

def get_storage_service() -> StorageService:
    """Get StorageService instance."""
    return StorageService()

def get_screenshot_service(
    token_service: TokenService = Depends(get_token_service),
    redis_service: RedisService = Depends(get_redis_service),
    kafka_service: KafkaService = Depends(get_kafka_service),
    storage_service: StorageService = Depends(get_storage_service)
) -> ScreenshotService:
    """Get ScreenshotService instance."""
    return ScreenshotService(
        token_service,
        redis_service,
        kafka_service,
        storage_service
    )