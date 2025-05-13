from pydantic import BaseModel, Field
import os
from typing import Optional

class KafkaConfig(BaseModel):
    bootstrap_servers: str = Field(default_factory=lambda: os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"))
    group_id: str = Field(default_factory=lambda: os.environ.get("KAFKA_GROUP_ID", "screenshot-service"))
    screenshots_requested_topic: str = Field(default_factory=lambda: os.environ.get("KAFKA_SCREENSHOTS_REQUESTED_TOPIC", "media.screenshots.requested"))
    screenshots_completed_topic: str = Field(default_factory=lambda: os.environ.get("KAFKA_SCREENSHOTS_COMPLETED_TOPIC", "media.screenshots.completed"))
    peer_available_topic: str = Field(default_factory=lambda: os.environ.get("KAFKA_PEER_AVAILABLE_TOPIC", "peer.available.with_requested_media"))

class RedisConfig(BaseModel):
    host: str = Field(default_factory=lambda: os.environ.get("REDIS_HOST", "localhost"))
    port: int = Field(default_factory=lambda: int(os.environ.get("REDIS_PORT", "6379")))
    db: int = Field(default_factory=lambda: int(os.environ.get("REDIS_DB", "0")))
    password: str = Field(default_factory=lambda: os.environ.get("REDIS_PASSWORD", ""))
    token_blacklist_prefix: str = Field(default_factory=lambda: os.environ.get("REDIS_TOKEN_BLACKLIST_PREFIX", "screenshot:token:blacklist:"))
    pending_requests_prefix: str = Field(default_factory=lambda: os.environ.get("REDIS_PENDING_REQUESTS_PREFIX", "screenshot:pending:"))

class MinioConfig(BaseModel):
    endpoint: str = Field(default_factory=lambda: os.environ.get("MINIO_ENDPOINT", "localhost:9000"))
    access_key: str = Field(default_factory=lambda: os.environ.get("MINIO_ACCESS_KEY", "minioadmin"))
    secret_key: str = Field(default_factory=lambda: os.environ.get("MINIO_SECRET_KEY", "minioadmin"))
    secure: bool = Field(default_factory=lambda: os.environ.get("MINIO_SECURE", "false").lower() == "true")
    bucket_name: str = Field(default_factory=lambda: os.environ.get("MINIO_BUCKET_NAME", "screenshots"))

class JWTConfig(BaseModel):
    secret_key: str = Field(default_factory=lambda: os.environ.get("JWT_SECRET_KEY", "secret"))
    algorithm: str = Field(default_factory=lambda: os.environ.get("JWT_ALGORITHM", "HS256"))
    token_expire_minutes: int = Field(default_factory=lambda: int(os.environ.get("JWT_TOKEN_EXPIRE_MINUTES", "30")))

class ServiceConfig(BaseModel):
    peer_registry_url: str = Field(default_factory=lambda: os.environ.get("PEER_REGISTRY_URL", "http://peer-registry:8000"))
    edge_service_url: str = Field(default_factory=lambda: os.environ.get("EDGE_SERVICE_URL", "http://edge-service:8000"))
    max_screenshots_per_request: int = Field(default_factory=lambda: int(os.environ.get("MAX_SCREENSHOTS_PER_REQUEST", "10")))
    pending_request_ttl_hours: int = Field(default_factory=lambda: int(os.environ.get("PENDING_REQUEST_TTL_HOURS", "24")))

class AppConfig(BaseModel):
    kafka: KafkaConfig = Field(default_factory=KafkaConfig)
    redis: RedisConfig = Field(default_factory=RedisConfig)
    minio: MinioConfig = Field(default_factory=MinioConfig)
    jwt: JWTConfig = Field(default_factory=JWTConfig)
    service: ServiceConfig = Field(default_factory=ServiceConfig)

# Singleton config instance
config = AppConfig()