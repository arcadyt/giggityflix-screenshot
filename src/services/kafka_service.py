import json
import threading
import logging
from typing import Callable, Dict, List, Any
from confluent_kafka import Consumer, Producer, KafkaError, KafkaException

from config import config
from models import PeerWithMedia, ScreenshotRequest

logger = logging.getLogger(__name__)


class KafkaService:
    def __init__(self):
        self.kafka_config = config.kafka
        self.producer = Producer({
            'bootstrap.servers': self.kafka_config.bootstrap_servers,
            'client.id': f'{self.kafka_config.group_id}-producer'
        })
        self.consumer = None
        self.running = False
        self.consumer_thread = None

    def publish_screenshots_completed(self, catalog_id: str, request_id: str,
                                      screenshot_urls: List[str]) -> None:
        """Publish a screenshots.completed event."""
        message = {
            'catalog_id': catalog_id,
            'request_id': request_id,
            'screenshot_urls': screenshot_urls,
            'status': 'completed'
        }

        self._publish_message(self.kafka_config.screenshots_completed_topic, message)

    def _publish_message(self, topic: str, message: Dict[str, Any]) -> None:
        """Publish a message to a Kafka topic."""
        try:
            # Convert message to JSON
            message_json = json.dumps(message)

            # Publish message
            self.producer.produce(
                topic,
                value=message_json.encode('utf-8'),
                callback=self._delivery_report
            )

            # Flush to ensure message is sent
            self.producer.flush()

        except Exception as e:
            logger.error(f"Failed to publish message to {topic}: {e}")

    def _delivery_report(self, err, msg) -> None:
        """Callback for message delivery reports."""
        if err is not None:
            logger.error(f'Message delivery failed: {err}')
        else:
            logger.debug(f'Message delivered to {msg.topic()} [{msg.partition()}]')

    def start_consuming(self,
                        screenshots_requested_handler: Callable[[ScreenshotRequest], None],
                        peer_available_handler: Callable[[PeerWithMedia], None]) -> None:
        """Start consuming Kafka messages."""
        if self.running:
            return

        self.running = True

        # Create consumer
        self.consumer = Consumer({
            'bootstrap.servers': self.kafka_config.bootstrap_servers,
            'group.id': self.kafka_config.group_id,
            'auto.offset.reset': 'earliest'
        })

        # Subscribe to topics
        self.consumer.subscribe([
            self.kafka_config.screenshots_requested_topic,
            self.kafka_config.peer_available_topic
        ])

        # Start consumer thread
        self.consumer_thread = threading.Thread(
            target=self._consume_loop,
            args=(screenshots_requested_handler, peer_available_handler),
            daemon=True
        )
        self.consumer_thread.start()

    def _consume_loop(self,
                      screenshots_requested_handler: Callable[[ScreenshotRequest], None],
                      peer_available_handler: Callable[[PeerWithMedia], None]) -> None:
        """Main consumer loop."""
        try:
            while self.running:
                # Poll for messages
                msg = self.consumer.poll(timeout=1.0)

                if msg is None:
                    continue

                if msg.error():
                    if msg.error().code() == KafkaError._PARTITION_EOF:
                        # End of partition event - not an error
                        continue
                    else:
                        logger.error(f"Kafka consumer error: {msg.error()}")
                        continue

                # Process message
                try:
                    # Parse message
                    message_json = msg.value().decode('utf-8')
                    message = json.loads(message_json)

                    # Handle message based on topic
                    if msg.topic() == self.kafka_config.screenshots_requested_topic:
                        # Create screenshot request
                        request = ScreenshotRequest(**message)
                        screenshots_requested_handler(request)

                    elif msg.topic() == self.kafka_config.peer_available_topic:
                        # Create peer with media
                        peer = PeerWithMedia(**message)
                        peer_available_handler(peer)

                except Exception as e:
                    logger.error(f"Failed to process message: {e}")

        except KafkaException as e:
            logger.error(f"Kafka exception: {e}")
        finally:
            self.consumer.close()

    def stop_consuming(self) -> None:
        """Stop consuming Kafka messages."""
        self.running = False
        if self.consumer_thread:
            self.consumer_thread.join(timeout=5.0)