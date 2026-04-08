from datetime import datetime, UTC

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage


SAMPLES = [
    ("sample-note.txt", b"Kibegi E2E sample text file\n"),
    ("sample-data.json", b'{\"service\":\"kibegi\",\"kind\":\"e2e\"}\n'),
    ("sample-sheet.csv", b"name,role\nAlice,student\nBob,lecturer\n"),
    ("sample-page.html", b"<html><body><h1>Kibegi E2E</h1></body></html>\n"),
    ("sample-config.yaml", b"app: kibegi\nenvironment: e2e\n"),
    ("sample-log.log", b"2026-04-08 08:00:00 INFO MinIO E2E sample\n"),
]


def main(cleanup=False):
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    prefix = f"e2e-samples/{timestamp}"

    print(f"Storage backend: {default_storage.__class__.__module__}.{default_storage.__class__.__name__}")
    print(f"Bucket: {getattr(settings, 'AWS_STORAGE_BUCKET_NAME', '')}")
    print(f"Endpoint: {getattr(settings, 'AWS_S3_ENDPOINT_URL', '')}")
    print(f"Base URL: {getattr(settings, 'MEDIA_URL', '')}")
    print(f"Upload prefix: {prefix}")

    uploaded_paths = []

    for file_name, content in SAMPLES:
        path = f"{prefix}/{file_name}"
        saved_path = default_storage.save(path, ContentFile(content, name=file_name))
        exists = default_storage.exists(saved_path)
        url = default_storage.url(saved_path)
        uploaded_paths.append(saved_path)

        print(f"Uploaded: {saved_path}")
        print(f"Exists: {exists}")
        print(f"URL: {url}")

        if not exists:
            raise RuntimeError(f"Upload verification failed for {saved_path}")

    print(f"Uploaded {len(uploaded_paths)} sample files successfully.")

    if cleanup:
        for saved_path in uploaded_paths:
            default_storage.delete(saved_path)
            print(f"Deleted: {saved_path}")
        print("Cleanup completed.")
    else:
        print("Cleanup skipped so you can inspect the files in the bucket.")


if __name__ == "__main__":
    main()
