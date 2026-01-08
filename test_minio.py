from django.core.files.base import ContentFile
from django.core.files.storage import default_storage

# Test upload
test_file = ContentFile(b"Hello MinIO!", name="test.txt")
path = default_storage.save("test-uploads/test.txt", test_file)
print(f"✅ File saved to: {path}")
print(f"✅ File URL: {default_storage.url(path)}")

# Check if file exists
exists = default_storage.exists(path)
print(f"✅ File exists: {exists}")

# Cleanup
default_storage.delete(path)
print(f"✅ Test file deleted")
