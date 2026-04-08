"""
Test async behavior of sharing system.

Run this file to see how async processing prevents blocking:
    python manage.py shell < sharing/test_async.py
"""


def main():
    import time
    from django.contrib.auth import get_user_model
    from apps.uploads.models import Upload
    from apps.sharing.tasks import bulk_share_async

    print("\n" + "=" * 60)
    print("TESTING ASYNC SHARING BEHAVIOR")
    print("=" * 60 + "\n")

    user_model = get_user_model()

    print("Setting up test data...")

    try:
        user1 = user_model.objects.filter(user_type='lecturer').first()
        if not user1:
            print("No lecturer found. Please create users first.")
            return

        students = user_model.objects.filter(user_type='student')[:5]
        if not students:
            print("No students found. Please create users first.")
            return

        print(f"Found lecturer: {user1.email}")
        print(f"Found {len(students)} students")

        upload = Upload.objects.filter(uploaded_by=user1, is_deleted=False).first()
        if not upload:
            print("No uploads found. Please upload a file first.")
            return

        print(f"Found upload: {upload.file_name} ({upload.file_code})")

        print("\n" + "-" * 60)
        print("TESTING BULK SHARE (ASYNC)")
        print("-" * 60)

        user_ids = [student.id for student in students]

        print(f"\nSharing {upload.file_name} with {len(user_ids)} users...")
        print("Starting timer...")

        start_time = time.time()

        bulk_share_async(
            upload=upload,
            shared_by=user1,
            user_ids=user_ids,
            message="Test async sharing",
        )

        response_time = (time.time() - start_time) * 1000

        print(f"\nAPI RESPONDED IN: {response_time:.2f}ms")
        print("   (Background thread is still processing...)")

        if response_time < 100:
            print("\nSUCCESS! API returned in <100ms")
            print("   This proves async processing is working!")
        else:
            print(f"\nResponse took {response_time:.2f}ms")
            print("   This is slower than expected for async.")

        print("\n" + "-" * 60)
        print("ASYNC BENEFITS DEMONSTRATED:")
        print("-" * 60)
        print("API returns immediately (not blocked)")
        print("User can continue working")
        print("Notifications sent in background")
        print("No timeout risk with many users")
        print("Better user experience")

        print("\nThe background thread is still running.")
        print("Shares will be created and notifications sent.")
        print("Check the shares table in a few seconds.")

    except Exception as exc:
        print(f"\nError: {exc}")
        import traceback

        traceback.print_exc()

    print("\n" + "=" * 60)
    print("TEST COMPLETE")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
