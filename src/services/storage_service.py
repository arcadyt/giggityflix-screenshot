import io
from typing import BinaryIO
import uuid
from minio import Minio
from minio.error import S3Error

from config import config


class StorageService:
    def __init__(self):
        minio_config = config.minio
        self.client = Minio(
            minio_config.endpoint,
            access_key=minio_config.access_key,
            secret_key=minio_config.secret_key,
            secure=minio_config.secure
        )
        self.bucket_name = minio_config.bucket_name
        self._ensure_bucket_exists()

    def _ensure_bucket_exists(self) -> None:
        """Ensure the screenshots bucket exists."""
        try:
            if not self.client.bucket_exists(self.bucket_name):
                self.client.make_bucket(self.bucket_name)
        except S3Error as e:
            raise RuntimeError(f"Failed to create bucket: {e}")

    def upload_screenshot(self, catalog_id: str, file_data: BinaryIO, content_type: str) -> str:
        """Upload a screenshot file to MinIO."""
        try:
            # Generate unique object name
            file_id = str(uuid.uuid4())
            object_name = f"{catalog_id}/{file_id}.jpg"

            # Get file size
            file_data.seek(0, io.SEEK_END)
            file_size = file_data.tell()
            file_data.seek(0)

            # Upload file
            self.client.put_object(
                bucket_name=self.bucket_name,
                object_name=object_name,
                data=file_data,
                length=file_size,
                content_type=content_type
            )

            return object_name
        except S3Error as e:
            raise RuntimeError(f"Failed to upload screenshot: {e}")

    def get_screenshot_url(self, object_name: str) -> str:
        """Get presigned URL for a screenshot."""
        try:
            # Generate presigned URL (valid for 1 hour)
            url = self.client.presigned_get_object(
                bucket_name=self.bucket_name,
                object_name=object_name,
                expires=3600
            )
            return url
        except S3Error as e:
            raise RuntimeError(f"Failed to generate presigned URL: {e}")