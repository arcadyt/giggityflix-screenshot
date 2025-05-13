import json
import pytest
from unittest.mock import MagicMock, patch, call

# Ensure the path is set up by importing conftest
from services.kafka_service import KafkaService
from models import ScreenshotRequest, PeerWithMedia


@pytest.fixture
def kafka_service():
    """Create a real KafkaService instance with mocked Producer."""
    with patch('confluent_kafka.Producer') as producer_mock:
        service = KafkaService()
        service.producer = producer_mock
        yield service


def test_publish_screenshots_completed(kafka_service):
    catalog_id = "catalog123"
    request_id = "request456"
    screenshot_urls = ["url1", "url2", "url3"]

    kafka_service.publish_screenshots_completed(catalog_id, request_id, screenshot_urls)

    kafka_service.producer.produce.assert_called_once()
    call_args = kafka_service.producer.produce.call_args
    assert call_args[0][0] == kafka_service.kafka_config.screenshots_completed_topic

    message_json = call_args[1]['value'].decode('utf-8')
    message = json.loads(message_json)

    assert message["catalog_id"] == catalog_id
    assert message["request_id"] == request_id
    assert message["screenshot_urls"] == screenshot_urls
    assert message["status"] == "completed"

    kafka_service.producer.flush.assert_called_once()


def test_start_consuming(kafka_service):
    # We need to patch the specific import location in the kafka_service module
    with patch('services.kafka_service.Consumer') as consumer_mock:
        with patch('services.kafka_service.threading.Thread') as thread_mock:
            # Create a mock consumer instance that will be returned
            consumer_instance = MagicMock()
            consumer_mock.return_value = consumer_instance

            # Create a mock thread instance
            thread_instance = MagicMock()
            thread_mock.return_value = thread_instance

            screenshots_requested_handler = MagicMock()
            peer_available_handler = MagicMock()

            # Call the method
            kafka_service.start_consuming(
                screenshots_requested_handler,
                peer_available_handler
            )

            # Verify Consumer was created
            consumer_mock.assert_called_once()

            # Get the config now that we know it was called
            consumer_config = consumer_mock.call_args[0][0]

            # Verify the config values
            assert consumer_config['bootstrap.servers'] == kafka_service.kafka_config.bootstrap_servers
            assert consumer_config['group.id'] == kafka_service.kafka_config.group_id
            assert consumer_config['auto.offset.reset'] == 'earliest'

            # Verify subscribe was called
            consumer_instance.subscribe.assert_called_once_with([
                kafka_service.kafka_config.screenshots_requested_topic,
                kafka_service.kafka_config.peer_available_topic
            ])

            # Verify thread was created and started
            thread_mock.assert_called_once()
            thread_instance.start.assert_called_once()

            # Verify running flag
            assert kafka_service.running is True


def test_start_consuming_already_running(kafka_service):
    with patch('confluent_kafka.Consumer') as consumer_mock:
        with patch('threading.Thread') as thread_mock:
            screenshots_requested_handler = MagicMock()
            peer_available_handler = MagicMock()

            kafka_service.running = True

            kafka_service.start_consuming(
                screenshots_requested_handler,
                peer_available_handler
            )

            consumer_mock.assert_not_called()
            thread_mock.assert_not_called()


def test_stop_consuming_not_running(kafka_service):
    kafka_service.running = False
    kafka_service.consumer_thread = None

    kafka_service.stop_consuming()


def test_stop_consuming_running(kafka_service):
    kafka_service.running = True
    thread_instance = MagicMock()
    kafka_service.consumer_thread = thread_instance

    kafka_service.stop_consuming()

    assert kafka_service.running is False
    thread_instance.join.assert_called_once_with(timeout=5.0)


def test_consume_loop_process_screenshot_requested(kafka_service, sample_screenshot_request):
    with patch('confluent_kafka.Consumer') as consumer_mock:
        mock_consumer = MagicMock()
        consumer_mock.return_value = mock_consumer

        mock_message = MagicMock()
        mock_message.error.return_value = None
        mock_message.topic.return_value = kafka_service.kafka_config.screenshots_requested_topic

        # Create message content based on sample request
        request_dict = {
            "catalog_id": sample_screenshot_request.catalog_id,
            "request_id": sample_screenshot_request.request_id,
            "requester_service": sample_screenshot_request.requester_service,
        }
        mock_message.value.return_value = json.dumps(request_dict).encode('utf-8')

        mock_consumer.poll.side_effect = [mock_message, None]

        screenshots_requested_handler = MagicMock()
        peer_available_handler = MagicMock()

        kafka_service.consumer = mock_consumer
        kafka_service.running = True

        def stop_after_one_message(*args, **kwargs):
            kafka_service.running = False
            return screenshots_requested_handler(*args, **kwargs)

        mock_handler = MagicMock(side_effect=stop_after_one_message)

        kafka_service._consume_loop(mock_handler, peer_available_handler)

        mock_handler.assert_called_once()
        handler_arg = mock_handler.call_args[0][0]
        assert isinstance(handler_arg, ScreenshotRequest)
        assert handler_arg.catalog_id == sample_screenshot_request.catalog_id
        assert handler_arg.request_id == sample_screenshot_request.request_id

        peer_available_handler.assert_not_called()


def test_consume_loop_process_peer_available(kafka_service, sample_peer_with_media):
    with patch('confluent_kafka.Consumer') as consumer_mock:
        mock_consumer = MagicMock()
        consumer_mock.return_value = mock_consumer

        mock_message = MagicMock()
        mock_message.error.return_value = None
        mock_message.topic.return_value = kafka_service.kafka_config.peer_available_topic

        # Create message content based on sample peer
        peer_data = {
            "peer_id": sample_peer_with_media.peer_id,
            "edge_id": sample_peer_with_media.edge_id,
            "catalog_ids": sample_peer_with_media.catalog_ids
        }
        mock_message.value.return_value = json.dumps(peer_data).encode('utf-8')

        mock_consumer.poll.side_effect = [mock_message, None]

        screenshots_requested_handler = MagicMock()
        peer_available_handler = MagicMock()

        kafka_service.consumer = mock_consumer
        kafka_service.running = True

        def stop_after_one_message(*args, **kwargs):
            kafka_service.running = False
            return peer_available_handler(*args, **kwargs)

        mock_handler = MagicMock(side_effect=stop_after_one_message)

        kafka_service._consume_loop(screenshots_requested_handler, mock_handler)

        mock_handler.assert_called_once()
        handler_arg = mock_handler.call_args[0][0]
        assert isinstance(handler_arg, PeerWithMedia)
        assert handler_arg.peer_id == sample_peer_with_media.peer_id
        assert handler_arg.edge_id == sample_peer_with_media.edge_id
        assert handler_arg.catalog_ids == sample_peer_with_media.catalog_ids

        screenshots_requested_handler.assert_not_called()


def test_consume_loop_handle_error(kafka_service):
    with patch('services.kafka_service.Consumer') as consumer_mock:
        mock_consumer = MagicMock()
        consumer_mock.return_value = mock_consumer

        mock_message = MagicMock()
        mock_error = MagicMock()
        mock_error.code.return_value = 1  # Not _PARTITION_EOF
        mock_message.error.return_value = mock_error

        screenshots_requested_handler = MagicMock()
        peer_available_handler = MagicMock()

        kafka_service.consumer = mock_consumer
        kafka_service.running = True

        # Fix: Make sure the function accepts keyword arguments
        def stop_loop(*args, **kwargs):
            kafka_service.running = False
            return mock_message

        mock_consumer.poll.side_effect = stop_loop

        kafka_service._consume_loop(screenshots_requested_handler, peer_available_handler)

        screenshots_requested_handler.assert_not_called()
        peer_available_handler.assert_not_called()