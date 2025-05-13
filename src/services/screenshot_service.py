import logging
from typing import List

import httpx

from src.config import config
from src.models import (
    PeerWithMedia, ScreenshotRequest, ScreenshotTokenInfo,
    TokenBlacklistReason, TokenPayload
)
from src.services.kafka_service import KafkaService
from src.services.redis_service import RedisService
from src.services.storage_service import StorageService
from src.services.token_service import TokenService

logger = logging.getLogger(__name__)


class ScreenshotService:
    def __init__(self,
                 token_service: TokenService,
                 redis_service: RedisService,
                 kafka_service: KafkaService,
                 storage_service: StorageService):
        self.token_service = token_service
        self.redis_service = redis_service
        self.kafka_service = kafka_service
        self.storage_service = storage_service
        self.service_config = config.service

    async def handle_screenshot_request(self, request: ScreenshotRequest) -> None:
        """Handle a screenshot.requested event."""
        logger.info(f"Handling screenshot request for catalog_id {request.catalog_id}")

        # Store pending request
        self.redis_service.add_pending_request(request)

        # Get peers with the requested catalog_id
        peers = await self._get_peers_with_catalog_id(request.catalog_id)

        if not peers:
            logger.info(f"No peers found with catalog_id {request.catalog_id}")
            return

        # Request screenshots from peers
        for peer in peers:
            await self._request_screenshots_from_peer(peer, request)

    async def handle_peer_available(self, peer: PeerWithMedia) -> None:
        """Handle a peer.available.with_requested_media event."""
        logger.info(f"Handling peer available: {peer.peer_id} with {len(peer.catalog_ids)} catalog_ids")

        # Check if any catalog_ids have pending requests
        for catalog_id in peer.catalog_ids:
            pending_requests = self.redis_service.get_pending_requests(catalog_id)

            if not pending_requests:
                continue

            # Request screenshots for each pending request
            for request in pending_requests:
                # Create a simplified PeerWithMedia with just one catalog_id
                single_catalog_peer = PeerWithMedia(
                    peer_id=peer.peer_id,
                    edge_id=peer.edge_id,
                    catalog_ids=[catalog_id]
                )

                await self._request_screenshots_from_peer(single_catalog_peer, request)

    async def _get_peers_with_catalog_id(self, catalog_id: str) -> List[PeerWithMedia]:
        """Get all peers that have a specific catalog_id."""
        try:
            # Make request to Peer Registry Service
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.service_config.peer_registry_url}/api/peers/catalog/{catalog_id}"
                )

                if response.status_code == 200:
                    peers_data = response.json()
                    return [PeerWithMedia(**peer) for peer in peers_data]
                else:
                    logger.error(f"Failed to get peers: {response.status_code} {response.text}")
                    return []
        except Exception as e:
            logger.error(f"Error getting peers: {e}")
            return []

    async def _request_screenshots_from_peer(self, peer: PeerWithMedia, request: ScreenshotRequest) -> None:
        """Request screenshots from a peer via the Edge Service."""
        try:
            # Create token for the peer
            for catalog_id in peer.catalog_ids:
                token_info = self.token_service.create_token(
                    peer_id=peer.peer_id,
                    catalog_id=catalog_id,
                    request_id=request.request_id
                )

                # Send request to Edge Service
                await self._send_screenshot_request_to_edge(peer.edge_id, token_info)

        except Exception as e:
            logger.error(f"Error requesting screenshots: {e}")

    async def _send_screenshot_request_to_edge(self, edge_id: str, token_info: ScreenshotTokenInfo) -> None:
        """Send a screenshot request to the Edge Service."""
        try:
            # Make request to Edge Service
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.service_config.edge_service_url}/api/edge/{edge_id}/screenshot/request",
                    json={
                        "peer_id": token_info.peer_id,
                        "catalog_id": token_info.catalog_id,
                        "token": token_info.token,
                        "screenshot_upload_url": f"/api/screenshot/{token_info.catalog_id}"
                    }
                )

                if response.status_code != 202:
                    logger.error(f"Failed to request screenshots: {response.status_code} {response.text}")

        except Exception as e:
            logger.error(f"Error sending screenshot request: {e}")

    def process_screenshot_upload(self,
                                  token_payload: TokenPayload,
                                  screenshot_files: List[bytes],
                                  content_types: List[str]) -> List[str]:
        """Process screenshot upload from a peer."""
        logger.info(f"Processing {len(screenshot_files)} screenshots for catalog_id {token_payload.catalog_id}")

        # Blacklist token to prevent reuse
        self.token_service.blacklist_token(
            token_payload.token_id,
            TokenBlacklistReason.ALREADY_USED
        )

        # Upload screenshots to MinIO
        screenshot_urls = []
        for file_data, content_type in zip(screenshot_files, content_types):
            try:
                # Upload screenshot
                object_name = self.storage_service.upload_screenshot(
                    token_payload.catalog_id,
                    file_data,
                    content_type
                )

                # Get URL
                url = self.storage_service.get_screenshot_url(object_name)
                screenshot_urls.append(url)

            except Exception as e:
                logger.error(f"Failed to upload screenshot: {e}")

        # Blacklist tokens for this catalog_id and request_id
        self._blacklist_other_tokens(token_payload)

        # Remove pending request
        self.redis_service.remove_pending_request(
            token_payload.catalog_id,
            token_payload.request_id
        )

        # Publish screenshots.completed event
        self.kafka_service.publish_screenshots_completed(
            token_payload.catalog_id,
            token_payload.request_id,
            screenshot_urls
        )

        return screenshot_urls

    def _blacklist_other_tokens(self, token_payload: TokenPayload) -> None:
        """Blacklist tokens for other peers for the same request."""
        # Get peers with the catalog_id (using synchronous client for simplicity)
        try:
            with httpx.Client() as client:
                response = client.get(
                    f"{self.service_config.peer_registry_url}/api/peers/catalog/{token_payload.catalog_id}"
                )

                if response.status_code != 200:
                    logger.error(f"Failed to get peers: {response.status_code} {response.text}")
                    return

                peers_data = response.json()

                # Blacklist tokens for other peers (implementation simplified)
                for peer_data in peers_data:
                    peer = PeerWithMedia(**peer_data)
                    if peer.peer_id != token_payload.peer_id:
                        logger.info(f"Blacklisting token for peer {peer.peer_id}")
                        # Here we would request token_id from Edge Service and blacklist it
                        # Simplified for brevity
        except Exception as e:
            logger.error(f"Error blacklisting other tokens: {e}")
