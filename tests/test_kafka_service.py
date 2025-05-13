import json
from unittest.mock import MagicMock, patch

import pytest
from confluent_kafka import KafkaError, KafkaException

from src.models import PeerWithMedia, ScreenshotRequest


@pytest.mark.unit
class TestKafkaService:
    def test_init(self, kafka_service, mock_producer):
        # Reset consumer to ensure it starts as None
        kafka_service.consumer = None

        # Verify producer was created with correct parameters
        assert kafka_service.producer == mock_producer
        assert kafka_service.consumer is None
        assert kafka_service.running is False
        assert kafka_service.consumer_thread is None

    def test_publish_screenshots_completed(self, kafka_service, mock_producer, test_data):
        catalog_id = test_data["catalog_id"]
        request_id = test_data["request_id"]
        screenshot_urls = test_data["screenshot_urls"]

        # Call the method
        kafka_service.publish_screenshots_completed(catalog_id, request_id, screenshot_urls)

        # Verify produce was called with correct parameters
        mock_producer.produce.assert_called_once()
        args, kwargs = mock_producer.produce.call_args

        assert args[0] == kafka_service.kafka_config.screenshots_completed_topic
        assert "value" in kwargs

        # Verify message JSON
        message_json = kwargs["value"].decode("utf-8")
        message = json.loads(message_json)

        assert message["catalog_id"] == catalog_id
        assert message["request_id"] == request_id
        assert message["screenshot_urls"] == screenshot_urls
        assert message["status"] == "completed"

        # Verify callback was provided
        assert "callback" in kwargs
        assert callable(kwargs["callback"])

        # Verify flush was called
        mock_producer.flush.assert_called_once()

    def test_delivery_report_success(self, kafka_service):
        # Create a mock message
        msg = MagicMock()
        msg.topic.return_value = "test-topic"
        msg.partition.return_value = 0

        # Call the method with no error
        with patch("src.services.kafka_service.logger") as logger_mock:
            kafka_service._delivery_report(None, msg)

            # Verify logger.debug was called
            logger_mock.debug.assert_called_once()
            assert "Message delivered" in logger_mock.debug.call_args[0][0]

    def test_delivery_report_error(self, kafka_service):
        # Create a mock error
        error = "Test error"

        # Call the method with an error
        with patch("src.services.kafka_service.logger") as logger_mock:
            kafka_service._delivery_report(error, None)

            # Verify logger.error was called
            logger_mock.error.assert_called_once()
            assert "Message delivery failed" in logger_mock.error.call_args[0][0]

    def test_start_consuming_already_running(self, kafka_service, mock_consumer):
        # Reset consumer to None first
        kafka_service.consumer = None
        # Set running flag to True
        kafka_service.running = True

        # Call the method
        screenshot_handler = MagicMock()
        peer_handler = MagicMock()

        kafka_service.start_consuming(screenshot_handler, peer_handler)

        # Verify consumer was not created
        assert kafka_service.consumer is None

    def test_start_consuming(self, kafka_service, mock_consumer):
        # Reset state first
        kafka_service.running = False
        kafka_service.consumer = None

        # Call the method
        with patch("src.services.kafka_service.Consumer", return_value=mock_consumer):
            with patch("src.services.kafka_service.threading.Thread") as thread_mock:
                thread_instance = MagicMock()
                thread_mock.return_value = thread_instance

                screenshot_handler = MagicMock()
                peer_handler = MagicMock()

                kafka_service.start_consuming(screenshot_handler, peer_handler)

                # Verify running flag was set
                assert kafka_service.running is True

                # Verify consumer was created
                assert kafka_service.consumer == mock_consumer

                # Verify subscribe was called with correct topics
                mock_consumer.subscribe.assert_called_once_with([
                    kafka_service.kafka_config.screenshots_requested_topic,
                    kafka_service.kafka_config.peer_available_topic
                ])

                # Verify thread was created and started
                thread_mock.assert_called_once()

                # Fix for call args - check that the Thread was created with the correct target
                # and args without assuming specific position
                call_kwargs = thread_mock.call_args.kwargs
                assert call_kwargs.get('target') == kafka_service._consume_loop
                assert call_kwargs.get('args') == (screenshot_handler, peer_handler)
                assert call_kwargs.get('daemon') is True

                thread_instance.start.assert_called_once()

    def test_stop_consuming_not_running(self, kafka_service):
        # Set running flag to False
        kafka_service.running = False
        kafka_service.consumer_thread = None

        # Call the method
        kafka_service.stop_consuming()

        # Verify nothing happened
        assert kafka_service.running is False

    def test_stop_consuming_running(self, kafka_service):
        # Set running flag to True
        kafka_service.running = True
        kafka_service.consumer_thread = MagicMock()

        # Call the method
        kafka_service.stop_consuming()

        # Verify running flag was cleared
        assert kafka_service.running is False

        # Verify thread was joined
        kafka_service.consumer_thread.join.assert_called_once_with(timeout=5.0)

    def test_consume_loop_screenshots_requested(self, kafka_service, mock_consumer, sample_screenshot_request):
        # Create handlers
        screenshots_requested_handler = MagicMock()
        peer_available_handler = MagicMock()

        # Set up mock message
        message = MagicMock()
        message.error.return_value = None
        message.topic.return_value = kafka_service.kafka_config.screenshots_requested_topic
        message.value.return_value = sample_screenshot_request.model_dump_json().encode("utf-8")

        # Set up consumer to return message once, then set running to False
        mock_consumer.poll.return_value = message

        # Set running flag to True
        kafka_service.running = True

        # Set up a side effect to stop the loop after one iteration
        def stop_after_call(request):
            kafka_service.running = False
            return None

        screenshots_requested_handler.side_effect = stop_after_call

        # Set consumer
        kafka_service.consumer = mock_consumer

        # Call the method
        kafka_service._consume_loop(screenshots_requested_handler, peer_available_handler)

        # Verify poll was called
        mock_consumer.poll.assert_called()

        # Verify handler was called with correct request
        screenshots_requested_handler.assert_called_once()
        handler_arg = screenshots_requested_handler.call_args[0][0]
        assert isinstance(handler_arg, ScreenshotRequest)
        assert handler_arg.catalog_id == sample_screenshot_request.catalog_id
        assert handler_arg.request_id == sample_screenshot_request.request_id

        # Verify other handler was not called
        peer_available_handler.assert_not_called()

        # Verify consumer was closed
        mock_consumer.close.assert_called_once()

    def test_consume_loop_peer_available(self, kafka_service, mock_consumer, sample_peer_with_media):
        # Create handlers
        screenshots_requested_handler = MagicMock()
        peer_available_handler = MagicMock()

        # Set up mock message
        message = MagicMock()
        message.error.return_value = None
        message.topic.return_value = kafka_service.kafka_config.peer_available_topic
        message.value.return_value = sample_peer_with_media.model_dump_json().encode("utf-8")

        # Set up consumer to return message once
        mock_consumer.poll.return_value = message

        # Set running flag to True
        kafka_service.running = True

        # Set up a side effect to stop the loop after one iteration
        def stop_after_call(peer):
            kafka_service.running = False
            return None

        peer_available_handler.side_effect = stop_after_call

        # Set consumer
        kafka_service.consumer = mock_consumer

        # Call the method
        kafka_service._consume_loop(screenshots_requested_handler, peer_available_handler)

        # Verify poll was called
        mock_consumer.poll.assert_called()

        # Verify handler was called with correct peer
        peer_available_handler.assert_called_once()
        handler_arg = peer_available_handler.call_args[0][0]
        assert isinstance(handler_arg, PeerWithMedia)
        assert handler_arg.peer_id == sample_peer_with_media.peer_id
        assert handler_arg.edge_id == sample_peer_with_media.edge_id
        assert handler_arg.catalog_ids == sample_peer_with_media.catalog_ids

        # Verify other handler was not called
        screenshots_requested_handler.assert_not_called()

        # Verify consumer was closed
        mock_consumer.close.assert_called_once()

    def test_consume_loop_message_error_partition_eof(self, kafka_service, mock_consumer):
        # Create handlers
        screenshots_requested_handler = MagicMock()
        peer_available_handler = MagicMock()

        # Set up mock message with _PARTITION_EOF error
        message = MagicMock()
        error = MagicMock()
        error.code.return_value = KafkaError._PARTITION_EOF
        message.error.return_value = error

        # Set up mock response sequence - first return the error message, then set running to False
        # to avoid recursion
        original_poll = mock_consumer.poll
        call_count = 0

        def mock_poll_with_count(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return message
            else:
                kafka_service.running = False
                return None

        mock_consumer.poll = mock_poll_with_count

        # Set running flag to True
        kafka_service.running = True

        # Set consumer
        kafka_service.consumer = mock_consumer

        # Call the method
        kafka_service._consume_loop(screenshots_requested_handler, peer_available_handler)

        # Verify poll was called
        assert call_count > 0

        # Verify no handlers were called
        screenshots_requested_handler.assert_not_called()
        peer_available_handler.assert_not_called()

        # Verify consumer was closed
        mock_consumer.close.assert_called_once()

    def test_consume_loop_message_error_other(self, kafka_service, mock_consumer):
        # Create handlers
        screenshots_requested_handler = MagicMock()
        peer_available_handler = MagicMock()

        # Set up mock message with non-_PARTITION_EOF error
        message = MagicMock()
        error = MagicMock()
        error.code.return_value = KafkaError._ALL_BROKERS_DOWN
        message.error.return_value = error

        # Set up mock response sequence - first return the error message, then set running to False
        original_poll = mock_consumer.poll
        call_count = 0

        def mock_poll_with_count(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return message
            else:
                kafka_service.running = False
                return None

        mock_consumer.poll = mock_poll_with_count

        # Set running flag to True
        kafka_service.running = True

        # Set consumer
        kafka_service.consumer = mock_consumer

        # Call the method with logger mock
        with patch("src.services.kafka_service.logger") as logger_mock:
            kafka_service._consume_loop(screenshots_requested_handler, peer_available_handler)

            # Verify poll was called
            assert call_count > 0

            # Verify logger.error was called
            logger_mock.error.assert_called_once()
            assert "Kafka consumer error" in logger_mock.error.call_args[0][0]

            # Verify no handlers were called
            screenshots_requested_handler.assert_not_called()
            peer_available_handler.assert_not_called()

            # Verify consumer was closed
            mock_consumer.close.assert_called_once()

    def test_consume_loop_kafka_exception(self, kafka_service, mock_consumer):
        # Create handlers
        screenshots_requested_handler = MagicMock()
        peer_available_handler = MagicMock()

        # Set up consumer to raise KafkaException
        mock_consumer.poll.side_effect = KafkaException("Kafka error")

        # Set running flag to True
        kafka_service.running = True

        # Set consumer
        kafka_service.consumer = mock_consumer

        # Call the method with logger mock
        with patch("src.services.kafka_service.logger") as logger_mock:
            kafka_service._consume_loop(screenshots_requested_handler, peer_available_handler)

            # Verify poll was called
            mock_consumer.poll.assert_called_once()

            # Verify logger.error was called
            logger_mock.error.assert_called_once()
            assert "Kafka exception" in logger_mock.error.call_args[0][0]

            # Verify no handlers were called
            screenshots_requested_handler.assert_not_called()
            peer_available_handler.assert_not_called()

            # Verify consumer was closed
            mock_consumer.close.assert_called_once()
