from unittest.mock import call

from src.models import TokenBlacklistReason
from tests.conftest import *  # Import all fixtures


@pytest.mark.unit
class TestScreenshotService:
    @pytest.mark.asyncio
    async def test_handle_screenshot_request_no_peers(self, screenshot_service, sample_screenshot_request):
        # Setup redis_service to store request
        screenshot_service.redis_service.add_pending_request = MagicMock()

        # Setup _get_peers_with_catalog_id to return empty list
        screenshot_service._get_peers_with_catalog_id = AsyncMock(return_value=[])

        # Call the method
        await screenshot_service.handle_screenshot_request(sample_screenshot_request)

        # Verify redis_service.add_pending_request was called
        screenshot_service.redis_service.add_pending_request.assert_called_once_with(sample_screenshot_request)

        # Verify _get_peers_with_catalog_id was called
        screenshot_service._get_peers_with_catalog_id.assert_called_once_with(sample_screenshot_request.catalog_id)

    @pytest.mark.asyncio
    async def test_handle_screenshot_request_with_peers(self, screenshot_service, sample_screenshot_request,
                                                        sample_peer_with_media):
        # Setup redis_service to store request
        screenshot_service.redis_service.add_pending_request = MagicMock()

        # Setup _get_peers_with_catalog_id to return peers
        screenshot_service._get_peers_with_catalog_id = AsyncMock(return_value=[sample_peer_with_media])

        # Setup _request_screenshots_from_peer
        screenshot_service._request_screenshots_from_peer = AsyncMock()

        # Call the method
        await screenshot_service.handle_screenshot_request(sample_screenshot_request)

        # Verify redis_service.add_pending_request was called
        screenshot_service.redis_service.add_pending_request.assert_called_once_with(sample_screenshot_request)

        # Verify _get_peers_with_catalog_id was called
        screenshot_service._get_peers_with_catalog_id.assert_called_once_with(sample_screenshot_request.catalog_id)

        # Verify _request_screenshots_from_peer was called
        screenshot_service._request_screenshots_from_peer.assert_called_once_with(
            sample_peer_with_media, sample_screenshot_request
        )

    @pytest.mark.asyncio
    async def test_handle_peer_available_no_pending_requests(self, screenshot_service, sample_peer_with_media):
        # Setup redis_service to return no pending requests
        screenshot_service.redis_service.get_pending_requests = MagicMock(return_value=[])

        # Call the method
        await screenshot_service.handle_peer_available(sample_peer_with_media)

        # Verify redis_service.get_pending_requests was called for each catalog_id
        calls = [
            call(catalog_id) for catalog_id in sample_peer_with_media.catalog_ids
        ]
        screenshot_service.redis_service.get_pending_requests.assert_has_calls(calls)

    @pytest.mark.asyncio
    async def test_handle_peer_available_with_pending_requests(
            self, screenshot_service, sample_peer_with_media, sample_screenshot_request
    ):
        # Setup redis_service to return pending requests for first catalog_id
        def get_pending_requests(catalog_id):
            if catalog_id == sample_peer_with_media.catalog_ids[0]:
                return [sample_screenshot_request]
            return []

        screenshot_service.redis_service.get_pending_requests = MagicMock(side_effect=get_pending_requests)

        # Setup _request_screenshots_from_peer
        screenshot_service._request_screenshots_from_peer = AsyncMock()

        # Call the method
        await screenshot_service.handle_peer_available(sample_peer_with_media)

        # Verify redis_service.get_pending_requests was called for each catalog_id
        calls = [
            call(catalog_id) for catalog_id in sample_peer_with_media.catalog_ids
        ]
        screenshot_service.redis_service.get_pending_requests.assert_has_calls(calls)

        # Verify _request_screenshots_from_peer was called
        screenshot_service._request_screenshots_from_peer.assert_called_once()
        peer_arg = screenshot_service._request_screenshots_from_peer.call_args[0][0]
        request_arg = screenshot_service._request_screenshots_from_peer.call_args[0][1]

        assert isinstance(peer_arg, PeerWithMedia)
        assert peer_arg.peer_id == sample_peer_with_media.peer_id
        assert peer_arg.edge_id == sample_peer_with_media.edge_id
        assert peer_arg.catalog_ids == [sample_peer_with_media.catalog_ids[0]]  # Only first catalog_id

        assert request_arg == sample_screenshot_request

    @pytest.mark.asyncio
    async def test_get_peers_with_catalog_id_success(self, screenshot_service, test_data, sample_peer_with_media,
                                                     mock_httpx_client):
        catalog_id = test_data["catalog_id"]

        # Setup httpx client to return peers
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = [sample_peer_with_media.model_dump()]
        mock_httpx_client.get.return_value = response

        # Call the method
        with patch("httpx.AsyncClient", return_value=mock_httpx_client):
            result = await screenshot_service._get_peers_with_catalog_id(catalog_id)

        # Verify httpx client was called with correct URL
        expected_url = f"{screenshot_service.service_config.peer_registry_url}/api/peers/catalog/{catalog_id}"
        mock_httpx_client.get.assert_called_once_with(expected_url)

        # Verify result
        assert len(result) == 1
        assert isinstance(result[0], PeerWithMedia)
        assert result[0].peer_id == sample_peer_with_media.peer_id
        assert result[0].edge_id == sample_peer_with_media.edge_id
        assert result[0].catalog_ids == sample_peer_with_media.catalog_ids

    @pytest.mark.asyncio
    async def test_get_peers_with_catalog_id_error(self, screenshot_service, test_data, mock_httpx_client):
        catalog_id = test_data["catalog_id"]

        # Setup httpx client to return error
        response = MagicMock()
        response.status_code = 500
        response.text = "Internal Server Error"
        mock_httpx_client.get.return_value = response

        # Call the method
        with patch("httpx.AsyncClient", return_value=mock_httpx_client):
            with patch("src.services.screenshot_service.logger") as logger_mock:
                result = await screenshot_service._get_peers_with_catalog_id(catalog_id)

                # Verify logger.error was called
                logger_mock.error.assert_called_once()
                assert "Failed to get peers" in logger_mock.error.call_args[0][0]

        # Verify result is empty list
        assert result == []

    @pytest.mark.asyncio
    async def test_get_peers_with_catalog_id_exception(self, screenshot_service, test_data):
        catalog_id = test_data["catalog_id"]

        # Setup httpx.AsyncClient to raise exception
        with patch("httpx.AsyncClient") as client_mock:
            client_mock.side_effect = Exception("Test exception")

            # Call the method
            with patch("src.services.screenshot_service.logger") as logger_mock:
                result = await screenshot_service._get_peers_with_catalog_id(catalog_id)

                # Verify logger.error was called
                logger_mock.error.assert_called_once()
                assert "Error getting peers" in logger_mock.error.call_args[0][0]

        # Verify result is empty list
        assert result == []

    @pytest.mark.asyncio
    async def test_request_screenshots_from_peer(
            self, screenshot_service, sample_peer_with_media, sample_screenshot_request, sample_token_info
    ):
        # Setup token_service to create token
        screenshot_service.token_service.create_token = MagicMock(return_value=sample_token_info)

        # Setup _send_screenshot_request_to_edge
        screenshot_service._send_screenshot_request_to_edge = AsyncMock()

        # Call the method
        await screenshot_service._request_screenshots_from_peer(sample_peer_with_media, sample_screenshot_request)

        # Verify token_service.create_token was called for each catalog_id
        calls = []
        for catalog_id in sample_peer_with_media.catalog_ids:
            calls.append(call(
                peer_id=sample_peer_with_media.peer_id,
                catalog_id=catalog_id,
                request_id=sample_screenshot_request.request_id
            ))

        screenshot_service.token_service.create_token.assert_has_calls(calls)

        # Verify _send_screenshot_request_to_edge was called for each catalog_id
        calls = []
        for _ in sample_peer_with_media.catalog_ids:
            calls.append(call(sample_peer_with_media.edge_id, sample_token_info))

        screenshot_service._send_screenshot_request_to_edge.assert_has_calls(calls)

    @pytest.mark.asyncio
    async def test_request_screenshots_from_peer_exception(
            self, screenshot_service, sample_peer_with_media, sample_screenshot_request
    ):
        # Setup token_service to raise exception
        screenshot_service.token_service.create_token = MagicMock(side_effect=Exception("Test exception"))

        # Call the method
        with patch("src.services.screenshot_service.logger") as logger_mock:
            await screenshot_service._request_screenshots_from_peer(sample_peer_with_media, sample_screenshot_request)

            # Verify logger.error was called
            logger_mock.error.assert_called_once()
            assert "Error requesting screenshots" in logger_mock.error.call_args[0][0]

    @pytest.mark.asyncio
    async def test_send_screenshot_request_to_edge_success(
            self, screenshot_service, test_data, sample_token_info, mock_httpx_client
    ):
        edge_id = test_data["edge_id"]

        # Setup httpx client to return success
        response = MagicMock()
        response.status_code = 202
        mock_httpx_client.post.return_value = response

        # Call the method
        with patch("httpx.AsyncClient", return_value=mock_httpx_client):
            await screenshot_service._send_screenshot_request_to_edge(edge_id, sample_token_info)

        # Verify httpx client was called with correct URL and data
        expected_url = f"{screenshot_service.service_config.edge_service_url}/api/edge/{edge_id}/screenshot/request"
        expected_json = {
            "peer_id": sample_token_info.peer_id,
            "catalog_id": sample_token_info.catalog_id,
            "token": sample_token_info.token,
            "screenshot_upload_url": f"/api/screenshot/{sample_token_info.catalog_id}"
        }

        mock_httpx_client.post.assert_called_once_with(expected_url, json=expected_json)

    @pytest.mark.asyncio
    async def test_send_screenshot_request_to_edge_error(
            self, screenshot_service, test_data, sample_token_info, mock_httpx_client
    ):
        edge_id = test_data["edge_id"]

        # Setup httpx client to return error
        response = MagicMock()
        response.status_code = 500
        response.text = "Internal Server Error"
        mock_httpx_client.post.return_value = response

        # Call the method
        with patch("httpx.AsyncClient", return_value=mock_httpx_client):
            with patch("src.services.screenshot_service.logger") as logger_mock:
                await screenshot_service._send_screenshot_request_to_edge(edge_id, sample_token_info)

                # Verify logger.error was called
                logger_mock.error.assert_called_once()
                assert "Failed to request screenshots" in logger_mock.error.call_args[0][0]

    @pytest.mark.asyncio
    async def test_send_screenshot_request_to_edge_exception(
            self, screenshot_service, test_data, sample_token_info
    ):
        edge_id = test_data["edge_id"]

        # Setup httpx.AsyncClient to raise exception
        with patch("httpx.AsyncClient") as client_mock:
            client_mock.side_effect = Exception("Test exception")

            # Call the method
            with patch("src.services.screenshot_service.logger") as logger_mock:
                await screenshot_service._send_screenshot_request_to_edge(edge_id, sample_token_info)

                # Verify logger.error was called
                logger_mock.error.assert_called_once()
                assert "Error sending screenshot request" in logger_mock.error.call_args[0][0]

    def test_process_screenshot_upload(
            self, screenshot_service, sample_token_payload, sample_screenshot_files, sample_content_types, test_data
    ):
        # Setup services
        screenshot_service.token_service.blacklist_token = MagicMock()
        screenshot_service.storage_service.upload_screenshot = MagicMock()
        screenshot_service.storage_service.get_screenshot_url = MagicMock()
        screenshot_service.redis_service.remove_pending_request = MagicMock()
        screenshot_service.kafka_service.publish_screenshots_completed = MagicMock()
        screenshot_service._blacklist_other_tokens = MagicMock()

        # Set up storage_service to return object names
        object_names = [f"{test_data['catalog_id']}/{i}.jpg" for i in range(len(sample_screenshot_files))]
        screenshot_service.storage_service.upload_screenshot.side_effect = object_names

        # Set up storage_service to return URLs
        screenshot_urls = [f"https://minio/{name}" for name in object_names]
        screenshot_service.storage_service.get_screenshot_url.side_effect = screenshot_urls

        # Call the method
        result = screenshot_service.process_screenshot_upload(
            sample_token_payload, sample_screenshot_files, sample_content_types
        )

        # Verify token_service.blacklist_token was called
        screenshot_service.token_service.blacklist_token.assert_called_once_with(
            sample_token_payload.token_id, TokenBlacklistReason.ALREADY_USED
        )

        # Verify storage_service.upload_screenshot was called for each file
        upload_calls = []
        for file_data, content_type in zip(sample_screenshot_files, sample_content_types):
            upload_calls.append(call(
                sample_token_payload.catalog_id, file_data, content_type
            ))

        screenshot_service.storage_service.upload_screenshot.assert_has_calls(upload_calls)

        # Verify storage_service.get_screenshot_url was called for each object name
        url_calls = [call(name) for name in object_names]
        screenshot_service.storage_service.get_screenshot_url.assert_has_calls(url_calls)

        # Verify _blacklist_other_tokens was called
        screenshot_service._blacklist_other_tokens.assert_called_once_with(sample_token_payload)

        # Verify redis_service.remove_pending_request was called
        screenshot_service.redis_service.remove_pending_request.assert_called_once_with(
            sample_token_payload.catalog_id, sample_token_payload.request_id
        )

        # Verify kafka_service.publish_screenshots_completed was called
        screenshot_service.kafka_service.publish_screenshots_completed.assert_called_once_with(
            sample_token_payload.catalog_id, sample_token_payload.request_id, screenshot_urls
        )

        # Verify result
        assert result == screenshot_urls

    def test_blacklist_other_tokens_success(self, screenshot_service, sample_token_payload, sample_peer_with_media):
        # Setup httpx client response
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = [
            {"peer_id": "other-peer-id", "edge_id": "other-edge-id", "catalog_ids": [sample_token_payload.catalog_id]},
            {"peer_id": sample_token_payload.peer_id, "edge_id": "test-edge-id",
             "catalog_ids": [sample_token_payload.catalog_id]}
        ]

        # Call the method
        with patch("httpx.Client") as client_mock:
            client_instance = MagicMock()
            client_instance.__enter__.return_value = client_instance
            client_instance.get.return_value = response
            client_mock.return_value = client_instance

            with patch("src.services.screenshot_service.logger") as logger_mock:
                screenshot_service._blacklist_other_tokens(sample_token_payload)

                # Verify logger.info was called for the other peer
                logger_mock.info.assert_called_once()
                assert "Blacklisting token for peer" in logger_mock.info.call_args[0][0]
                assert "other-peer-id" in logger_mock.info.call_args[0][0]

                # Verify httpx client was called with correct URL
                expected_url = f"{screenshot_service.service_config.peer_registry_url}/api/peers/catalog/{sample_token_payload.catalog_id}"
                client_instance.get.assert_called_once_with(expected_url)

    def test_blacklist_other_tokens_error(self, screenshot_service, sample_token_payload):
        # Setup httpx client response
        response = MagicMock()
        response.status_code = 500
        response.text = "Internal Server Error"

        # Call the method
        with patch("httpx.Client") as client_mock:
            client_instance = MagicMock()
            client_instance.__enter__.return_value = client_instance
            client_instance.get.return_value = response
            client_mock.return_value = client_instance

            with patch("src.services.screenshot_service.logger") as logger_mock:
                screenshot_service._blacklist_other_tokens(sample_token_payload)

                # Verify logger.error was called
                logger_mock.error.assert_called_once()
                assert "Failed to get peers" in logger_mock.error.call_args[0][0]

                # Verify httpx client was called with correct URL
                expected_url = f"{screenshot_service.service_config.peer_registry_url}/api/peers/catalog/{sample_token_payload.catalog_id}"
                client_instance.get.assert_called_once_with(expected_url)

    def test_blacklist_other_tokens_exception(self, screenshot_service, sample_token_payload):
        # Call the method with httpx.Client raising exception
        with patch("httpx.Client") as client_mock:
            client_mock.side_effect = Exception("Test exception")

            with patch("src.services.screenshot_service.logger") as logger_mock:
                screenshot_service._blacklist_other_tokens(sample_token_payload)

                # Verify logger.error was called
                logger_mock.error.assert_called_once()
                assert "Error blacklisting other tokens" in logger_mock.error.call_args[0][0]
