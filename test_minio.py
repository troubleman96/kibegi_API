from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.conf import settings


def main():
    test_file = ContentFile(b"Hello MinIO!", name="test.txt")
    path = default_storage.save("test-uploads/test.txt", test_file)
    print(f"File saved to: {path}")
    print(f"File URL: {default_storage.url(path)}")
    print(f"Storage backend: {default_storage.__class__.__module__}.{default_storage.__class__.__name__}")
    print(f"Bucket: {getattr(settings, 'AWS_STORAGE_BUCKET_NAME', '')}")
    print(f"Endpoint: {getattr(settings, 'AWS_S3_ENDPOINT_URL', '')}")

    exists = default_storage.exists(path)
    print(f"File exists: {exists}")

    default_storage.delete(path)
    print("Test file deleted")


if __name__ == "__main__":
    main()
