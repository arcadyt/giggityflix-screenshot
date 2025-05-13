import uuid

from tests.conftest import *  # Import all fixtures


# Create a mock S3Error class that can be raised as an exception
class MockS3Error(Exception):
    def __init__(self, message="Mocked S3 Error"):
        self.message = message
        super().__init__(self.message)


@pytest.mark.unit
class TestStorageService:
    def test_init_bucket_exists(self, mock_minio_client):
        # Reset mock to ensure clean state
        mock_minio_client.reset_mock()

        # Setup MinIO client to return True for bucket_exists
        mock_minio_client.bucket_exists.return_value = True

        # Create a new instance to trigger _ensure_bucket_exists
        with patch("src.services.storage_service.Minio", return_value=mock_minio_client):
            storage_service = StorageService()

        # Verify bucket_exists was called with correct bucket name
        mock_minio_client.bucket_exists.assert_called_once_with(storage_service.bucket_name)

        # Verify make_bucket was not called
        mock_minio_client.make_bucket.assert_not_called()

    def test_init_bucket_doesnt_exist(self, mock_minio_client):
        # Reset mock to ensure clean state
        mock_minio_client.reset_mock()

        # Setup MinIO client to return False for bucket_exists
        mock_minio_client.bucket_exists.return_value = False

        # Create a new instance to trigger _ensure_bucket_exists
        with patch("src.services.storage_service.Minio", return_value=mock_minio_client):
            storage_service = StorageService()

        # Verify bucket_exists was called with correct bucket name
        mock_minio_client.bucket_exists.assert_called_once_with(storage_service.bucket_name)

        # Verify make_bucket was called with correct bucket name
        mock_minio_client.make_bucket.assert_called_once_with(storage_service.bucket_name)

    def test_init_bucket_error(self, mock_minio_client):
        # Reset mock to ensure clean state
        mock_minio_client.reset_mock()

        # Setup MinIO client to raise a mock error
        mock_minio_client.bucket_exists.side_effect = MockS3Error("Access Denied")

        # Create a new instance to trigger _ensure_bucket_exists
        with patch("src.services.storage_service.Minio", return_value=mock_minio_client):
            with patch("src.services.storage_service.S3Error", MockS3Error):
                with pytest.raises(RuntimeError) as excinfo:
                    storage_service = StorageService()

                assert "Failed to create bucket" in str(excinfo.value)

    def test_upload_screenshot(self, storage_service, mock_minio_client, test_data):
        catalog_id = test_data["catalog_id"]
        file_data = io.BytesIO(b"fake-screenshot-data")
        content_type = "image/jpeg"

        # Create a UUID object with a known value
        file_id_hex = "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4"
        uuid_obj = uuid.UUID(file_id_hex)
        # The string representation will have hyphens
        file_id_str = str(uuid_obj)  # 'a1b2c3d4-e5f6-a1b2-c3d4-e5f6a1b2c3d4'

        # Call the method
        with patch("uuid.uuid4") as mock_uuid4:
            mock_uuid4.return_value = uuid_obj
            result = storage_service.upload_screenshot(catalog_id, file_data, content_type)

        # Verify put_object was called with correct parameters
        mock_minio_client.put_object.assert_called_once()
        args, kwargs = mock_minio_client.put_object.call_args

        assert kwargs["bucket_name"] == storage_service.bucket_name
        # Use the string representation with hyphens to match the actual format
        assert kwargs["object_name"] == f"{catalog_id}/{file_id_str}.jpg"
        assert kwargs["data"] == file_data
        assert kwargs["content_type"] == content_type

        # Verify result matches what the method returns
        assert result == f"{catalog_id}/{file_id_str}.jpg"

    def test_upload_screenshot_error(self, storage_service, mock_minio_client, test_data):
        catalog_id = test_data["catalog_id"]
        file_data = io.BytesIO(b"fake-screenshot-data")
        content_type = "image/jpeg"

        # Setup MinIO client to raise an error
        mock_minio_client.put_object.side_effect = MockS3Error("Internal Error")

        # Call the method and expect exception
        with patch("src.services.storage_service.S3Error", MockS3Error):
            with pytest.raises(RuntimeError) as excinfo:
                storage_service.upload_screenshot(catalog_id, file_data, content_type)

            assert "Failed to upload screenshot" in str(excinfo.value)

    def test_get_screenshot_url(self, storage_service, mock_minio_client):
        object_name = "test-catalog/test-uuid.jpg"
        presigned_url = "https://minio/presigned-url"

        # Setup MinIO client to return presigned URL
        mock_minio_client.presigned_get_object.return_value = presigned_url

        # Call the method
        result = storage_service.get_screenshot_url(object_name)

        # Verify presigned_get_object was called with correct parameters
        mock_minio_client.presigned_get_object.assert_called_once_with(
            bucket_name=storage_service.bucket_name,
            object_name=object_name,
            expires=3600
        )

        # Verify result
        assert result == presigned_url

    def test_get_screenshot_url_error(self, storage_service, mock_minio_client):
        object_name = "test-catalog/test-uuid.jpg"

        # Setup MinIO client to raise an error
        mock_minio_client.presigned_get_object.side_effect = MockS3Error("Internal Error")

        # Call the method and expect exception
        with patch("src.services.storage_service.S3Error", MockS3Error):
            with pytest.raises(RuntimeError) as excinfo:
                storage_service.get_screenshot_url(object_name)

            assert "Failed to generate presigned URL" in str(excinfo.value)
