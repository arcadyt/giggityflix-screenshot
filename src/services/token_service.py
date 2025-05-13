import uuid
from datetime import datetime, timedelta
from typing import Optional, Dict

from jose import jwt
from redis import Redis

from src.config import config
from src.models import TokenPayload, ScreenshotTokenInfo, TokenBlacklistReason


class TokenService:
    def __init__(self, redis_client: Redis):
        self.redis_client = redis_client
        self.jwt_config = config.jwt
        self.redis_config = config.redis

    def create_token(self, peer_id: str, catalog_id: str, request_id: str) -> ScreenshotTokenInfo:
        """Create a one-time JWT token for screenshot upload."""
        token_id = str(uuid.uuid4())

        # Set expiration time
        expires_delta = timedelta(minutes=self.jwt_config.token_expire_minutes)
        expire = datetime.utcnow() + expires_delta

        # Create token payload
        to_encode: Dict[str, str] = {
            "peer_id": peer_id,
            "catalog_id": catalog_id,
            "request_id": request_id,
            "token_id": token_id,
            "exp": expire.timestamp()
        }

        # Encode JWT
        encoded_jwt = jwt.encode(
            to_encode,
            self.jwt_config.secret_key,
            algorithm=self.jwt_config.algorithm
        )

        return ScreenshotTokenInfo(
            token=encoded_jwt,
            peer_id=peer_id,
            catalog_id=catalog_id,
            request_id=request_id,
            token_id=token_id
        )

    def validate_token(self, token: str) -> Optional[TokenPayload]:
        """Validate a token and return its payload if valid."""
        try:
            # Decode JWT
            payload = jwt.decode(
                token,
                self.jwt_config.secret_key,
                algorithms=[self.jwt_config.algorithm]
            )

            # Create payload model
            token_data = TokenPayload(
                peer_id=payload["peer_id"],
                catalog_id=payload["catalog_id"],
                request_id=payload["request_id"],
                token_id=payload["token_id"],
                exp=datetime.fromtimestamp(payload["exp"])
            )

            # Check if token is blacklisted
            blacklist_key = f"{self.redis_config.token_blacklist_prefix}{token_data.token_id}"
            if self.redis_client.exists(blacklist_key):
                return None

            return token_data
        except jwt.JWTError:
            return None

    def blacklist_token(self, token_id: str, reason: TokenBlacklistReason, ttl_hours: int = 24) -> None:
        """Blacklist a token."""
        blacklist_key = f"{self.redis_config.token_blacklist_prefix}{token_id}"
        self.redis_client.setex(
            blacklist_key,
            timedelta(hours=ttl_hours),
            reason.value
        )

    def get_blacklist_reason(self, token_id: str) -> Optional[TokenBlacklistReason]:
        """Get the reason a token was blacklisted."""
        blacklist_key = f"{self.redis_config.token_blacklist_prefix}{token_id}"
        reason_value = self.redis_client.get(blacklist_key)

        if not reason_value:
            return None

        return TokenBlacklistReason(reason_value.decode('utf-8'))
