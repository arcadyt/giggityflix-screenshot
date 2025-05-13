# Giggityflix Screenshot Service

Microservice for handling screenshot capture requests and uploads for the Giggityflix media streaming platform.

## Overview

This service:

- Receives screenshot requests via Kafka events
- Issues one-time JWT tokens to peers for authentication
- Handles screenshot uploads from peers
- Stores screenshots in MinIO object storage
- Publishes completion events

## Installation

```bash
# Install dependencies
poetry install

# Run service
poetry run python -m src.main
```

## Environment Variables

### Server Configuration

- `PORT`: HTTP server port (default: 8000)
- `LOG_LEVEL`: Logging level (default: info)

### Kafka Configuration

- `KAFKA_BOOTSTRAP_SERVERS`: Kafka broker addresses (default: localhost:9092)
- `KAFKA_GROUP_ID`: Consumer group ID (default: screenshot-service)
- `KAFKA_SCREENSHOTS_REQUESTED_TOPIC`: Topic for screenshot requests (default: media.screenshots.requested)
- `KAFKA_SCREENSHOTS_COMPLETED_TOPIC`: Topic for completed screenshots (default: media.screenshots.completed)
- `KAFKA_PEER_AVAILABLE_TOPIC`: Topic for available peers (default: peer.available.with_requested_media)

### Redis Configuration

- `REDIS_HOST`: Redis hostname (default: localhost)
- `REDIS_PORT`: Redis port (default: 6379)
- `REDIS_DB`: Redis database number (default: 0)
- `REDIS_PASSWORD`: Redis password (default: empty)
- `REDIS_TOKEN_BLACKLIST_PREFIX`: Prefix for blacklisted tokens (default: screenshot:token:blacklist:)
- `REDIS_PENDING_REQUESTS_PREFIX`: Prefix for pending requests (default: screenshot:pending:)

### MinIO Configuration

- `MINIO_ENDPOINT`: MinIO server endpoint (default: localhost:9000)
- `MINIO_ACCESS_KEY`: MinIO access key (default: minioadmin)
- `MINIO_SECRET_KEY`: MinIO secret key (default: minioadmin)
- `MINIO_SECURE`: Use HTTPS for MinIO (default: false)
- `MINIO_BUCKET_NAME`: Bucket for screenshots (default: screenshots)

### JWT Configuration

- `JWT_SECRET_KEY`: Secret key for JWT tokens (default: secret)
- `JWT_ALGORITHM`: JWT signing algorithm (default: HS256)
- `JWT_TOKEN_EXPIRE_MINUTES`: Token expiration in minutes (default: 30)

### Service Configuration

- `PEER_REGISTRY_URL`: URL of Peer Registry service (default: http://peer-registry:8000)
- `EDGE_SERVICE_URL`: URL of Edge service (default: http://edge-service:8000)
- `MAX_SCREENSHOTS_PER_REQUEST`: Maximum screenshots per request (default: 10)
- `PENDING_REQUEST_TTL_HOURS`: Time-to-live for pending requests (default: 24)

## API Endpoints

- `POST /api/screenshot/{catalog_id}`: Upload screenshots for a media item
    - Requires Bearer token in Authorization header
    - Accepts multipart/form-data with image files

## Event Flow

1. Service receives `media.screenshots.requested` events
2. Queries Peer Registry for peers with the requested media
3. Generates one-time tokens for peers
4. Sends requests to peers via Edge Service
5. Receives uploads from peers with valid tokens
6. Stores screenshots in MinIO
7. Publishes `media.screenshots.completed` events

## Development

```bash
# Run tests
poetry run pytest

# Run with auto-reload
poetry run uvicorn src.main:app --reload
```