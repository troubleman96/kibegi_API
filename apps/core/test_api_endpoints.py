from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework import status
from rest_framework.test import APITestCase, APIClient

from apps.authentication.models import PasswordResetOTP, User
from apps.classes.models import Class, Membership
from apps.friends.models import Friendship
from apps.notifications.models import Notification
from apps.sharing.models import SharedFile
from apps.storage.models import StorageUsageHistory
from apps.uploads.models import Upload


class BaseAPITestCase(APITestCase):
    def setUp(self):
        self.lecturer = User.objects.create_user(
            email="lecturer@test.com",
            full_name="Lecturer User",
            user_type="lecturer",
            password="StrongPass123!",
        )
        self.student = User.objects.create_user(
            email="student@test.com",
            full_name="Student User",
            user_type="student",
            password="StrongPass123!",
        )
        self.other_student = User.objects.create_user(
            email="other@test.com",
            full_name="Other Student",
            user_type="student",
            password="StrongPass123!",
        )
        self.outsider = User.objects.create_user(
            email="outsider@test.com",
            full_name="Outsider User",
            user_type="student",
            password="StrongPass123!",
        )

        self.class_obj = Class.objects.create(
            name="Algorithms",
            description="Core algorithms class",
            creator=self.lecturer,
            is_verified=True,
            is_public=False,
        )
        Membership.objects.create(user=self.lecturer, class_obj=self.class_obj, role="lecturer")
        Membership.objects.create(user=self.student, class_obj=self.class_obj, role="student")
        Membership.objects.create(user=self.other_student, class_obj=self.class_obj, role="student")

    def api_client_for(self, user):
        client = APIClient()
        client.force_authenticate(user=user)
        return client

    def make_upload(self, uploader=None, class_obj=None, name="notes.txt", content=b"class notes"):
        uploader = uploader or self.lecturer
        class_obj = class_obj or self.class_obj
        file_obj = SimpleUploadedFile(name, content, content_type="text/plain")
        return Upload.objects.create(
            uploader=uploader,
            class_obj=class_obj,
            file=file_obj,
            file_name=name,
            file_size=len(content),
        )


class AuthenticationEndpointTests(BaseAPITestCase):
    @patch("apps.authentication.views.EmailService.send_registration_otp")
    def test_register_verify_login_profile_and_change_password_flow(self, send_registration_otp):
        response = self.client.post(
            "/api/v1/auth/register/",
            {
                "email": "fresh@test.com",
                "full_name": "Fresh User",
                "user_type": "student",
                "password": "StrongPass123!",
                "confirm_password": "StrongPass123!",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        created_user = User.objects.get(email="fresh@test.com")
        self.assertFalse(created_user.is_active)
        otp = PasswordResetOTP.objects.filter(email="fresh@test.com").latest("created_at")
        send_registration_otp.assert_called_once()

        verify_response = self.client.post(
            "/api/v1/auth/register/verify/",
            {"email": "fresh@test.com", "otp": otp.code},
            format="json",
        )
        self.assertEqual(verify_response.status_code, status.HTTP_200_OK)
        created_user.refresh_from_db()
        self.assertTrue(created_user.is_active)
        self.assertIn("access", verify_response.data["data"]["tokens"])

        login_response = self.client.post(
            "/api/v1/auth/login/",
            {"email": "fresh@test.com", "password": "StrongPass123!"},
            format="json",
        )
        self.assertEqual(login_response.status_code, status.HTTP_200_OK)

        client = self.api_client_for(created_user)
        profile_response = client.get("/api/v1/auth/profile/")
        self.assertEqual(profile_response.status_code, status.HTTP_200_OK)
        self.assertEqual(profile_response.data["data"]["email"], "fresh@test.com")

        change_password_response = client.post(
            "/api/v1/auth/change-password/",
            {
                "current_password": "StrongPass123!",
                "new_password": "BetterPass123!",
                "confirm_password": "BetterPass123!",
            },
            format="json",
        )
        self.assertEqual(change_password_response.status_code, status.HTTP_200_OK)

        relogin_response = self.client.post(
            "/api/v1/auth/login/",
            {"email": "fresh@test.com", "password": "BetterPass123!"},
            format="json",
        )
        self.assertEqual(relogin_response.status_code, status.HTTP_200_OK)

    @patch("apps.authentication.views.EmailService.send_password_reset_otp")
    def test_password_reset_endpoints(self, send_password_reset_otp):
        response = self.client.post(
            "/api/v1/auth/password-reset/",
            {"email": self.student.email},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        send_password_reset_otp.assert_called_once()

        otp = PasswordResetOTP.objects.filter(email=self.student.email).latest("created_at")
        verify_response = self.client.post(
            "/api/v1/auth/password-reset/verify/",
            {"email": self.student.email, "otp": otp.code},
            format="json",
        )
        self.assertEqual(verify_response.status_code, status.HTTP_200_OK)
        reset_token = verify_response.data["data"]["reset_token"]

        confirm_response = self.client.post(
            "/api/v1/auth/password-reset-confirm/",
            {
                "token": reset_token,
                "new_password": "ResetPass123!",
                "confirm_password": "ResetPass123!",
            },
            format="json",
        )
        self.assertEqual(confirm_response.status_code, status.HTTP_200_OK)

        login_response = self.client.post(
            "/api/v1/auth/login/",
            {"email": self.student.email, "password": "ResetPass123!"},
            format="json",
        )
        self.assertEqual(login_response.status_code, status.HTTP_200_OK)


class ClassesEndpointTests(BaseAPITestCase):
    def test_class_create_search_join_members_and_leave_flow(self):
        lecturer_client = self.api_client_for(self.lecturer)
        create_response = lecturer_client.post(
            "/api/v1/classes/",
            {"name": "Databases", "description": "DB class", "is_public": True},
            format="json",
        )
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        created_class = Class.objects.get(name="Databases")

        student_client = self.api_client_for(self.outsider)
        search_response = student_client.get("/api/v1/classes/search/?q=Databases")
        self.assertEqual(search_response.status_code, status.HTTP_200_OK)

        join_response = student_client.post(
            "/api/v1/classes/join/",
            {"class_code": created_class.class_code},
            format="json",
        )
        self.assertEqual(join_response.status_code, status.HTTP_200_OK)
        self.assertTrue(created_class.members.filter(id=self.outsider.id).exists())

        members_response = student_client.get(f"/api/v1/classes/{created_class.id}/members/")
        self.assertEqual(members_response.status_code, status.HTTP_200_OK)

        leave_response = student_client.post(f"/api/v1/classes/{created_class.id}/leave/")
        self.assertEqual(leave_response.status_code, status.HTTP_200_OK)
        self.assertFalse(created_class.members.filter(id=self.outsider.id).exists())


class UploadsFilesAndStorageEndpointTests(BaseAPITestCase):
    def test_upload_and_storage_endpoints_track_usage(self):
        lecturer_client = self.api_client_for(self.lecturer)
        upload_response = lecturer_client.post(
            "/api/v1/uploads/",
            {
                "class_obj": str(self.class_obj.id),
                "file": SimpleUploadedFile("lecture.txt", b"lecture material", content_type="text/plain"),
                "file_name": "lecture.txt",
            },
            format="multipart",
        )
        self.assertEqual(upload_response.status_code, status.HTTP_201_CREATED)
        upload = Upload.objects.get(file_name="lecture.txt")

        storage_response = lecturer_client.get("/api/v1/storage/")
        self.assertEqual(storage_response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(storage_response.data["data"]["used_storage_bytes"], upload.file_size)

        info_response = lecturer_client.get("/api/v1/storage/info/")
        self.assertEqual(info_response.status_code, status.HTTP_200_OK)

        StorageUsageHistory.objects.create(user_storage=self.lecturer.storage, used_storage_bytes=upload.file_size)
        history_response = lecturer_client.get("/api/v1/storage/history/")
        self.assertEqual(history_response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(history_response.data["data"]), 1)

        recalc_response = lecturer_client.post("/api/v1/storage/recalculate/")
        self.assertEqual(recalc_response.status_code, status.HTTP_200_OK)

    def test_upload_detail_requires_membership_or_share(self):
        upload = self.make_upload()

        member_client = self.api_client_for(self.student)
        allowed_response = member_client.get(f"/api/v1/uploads/{upload.file_code}/")
        self.assertEqual(allowed_response.status_code, status.HTTP_200_OK)

        outsider_client = self.api_client_for(self.outsider)
        denied_response = outsider_client.get(f"/api/v1/uploads/{upload.file_code}/")
        self.assertEqual(denied_response.status_code, status.HTTP_403_FORBIDDEN)

    def test_files_endpoints_return_file_url_and_shared_by(self):
        upload = self.make_upload()
        SharedFile.objects.create(
            upload=upload,
            shared_by=self.lecturer,
            shared_with=self.student,
            status="accepted",
            message="Please review",
        )

        student_client = self.api_client_for(self.student)
        shared_response = student_client.get("/api/v1/files/shared-with-me/")
        self.assertEqual(shared_response.status_code, status.HTTP_200_OK)
        file_payload = shared_response.data["data"][0]
        self.assertIn(upload.file.name, file_payload["file_url"])
        self.assertEqual(file_payload["shared_by"]["email"], self.lecturer.email)

        detail_response = student_client.get(f"/api/v1/files/{upload.file_code}/")
        self.assertEqual(detail_response.status_code, status.HTTP_200_OK)
        self.assertEqual(detail_response.data["data"]["shared_by"]["email"], self.lecturer.email)

        all_files_response = student_client.get("/api/v1/files/all/")
        self.assertEqual(all_files_response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(all_files_response.data["data"]), 1)

    @patch("django.core.files.storage.FileSystemStorage.delete")
    def test_permanent_delete_endpoints_use_storage_backend_delete(self, delete_file):
        upload = self.make_upload(uploader=self.student)
        upload.soft_delete()

        student_client = self.api_client_for(self.student)
        response = student_client.delete(f"/api/v1/files/{upload.file_code}/permanent-delete/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        delete_file.assert_called_once()
        self.assertFalse(Upload.objects.filter(id=upload.id).exists())


class FriendsAndNotificationsEndpointTests(BaseAPITestCase):
    def test_friends_endpoints_cover_request_lifecycle(self):
        student_client = self.api_client_for(self.student)

        search_response = student_client.get("/api/v1/friends/search/?q=Other")
        self.assertEqual(search_response.status_code, status.HTTP_200_OK)

        add_response = student_client.post(
            "/api/v1/friends/add/",
            {"user_id": self.other_student.id},
            format="json",
        )
        self.assertEqual(add_response.status_code, status.HTTP_201_CREATED)
        friendship = Friendship.objects.get(user=self.student, friend=self.other_student)

        incoming_client = self.api_client_for(self.other_student)
        incoming_response = incoming_client.get("/api/v1/friends/requests/incoming/")
        self.assertEqual(incoming_response.status_code, status.HTTP_200_OK)

        accept_response = incoming_client.post(f"/api/v1/friends/{friendship.id}/accept/")
        self.assertEqual(accept_response.status_code, status.HTTP_200_OK)

        nickname_response = student_client.patch(
            f"/api/v1/friends/{friendship.id}/nickname/",
            {"nickname": "Study Buddy"},
            format="json",
        )
        self.assertEqual(nickname_response.status_code, status.HTTP_200_OK)

        list_response = student_client.get("/api/v1/friends/")
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)

        remove_response = student_client.delete(f"/api/v1/friends/{friendship.id}/")
        self.assertEqual(remove_response.status_code, status.HTTP_200_OK)

    def test_notification_endpoints_work(self):
        Notification.objects.create(
            user=self.student,
            notification_type="friend_request",
            content="You have a new request",
            related_object_id="123",
        )
        Notification.objects.create(
            user=self.student,
            notification_type="share_request",
            content="A file was shared with you",
            related_object_id="456",
        )

        client = self.api_client_for(self.student)
        list_response = client.get("/api/v1/notifications/")
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(list_response.data["data"]["unread_count"], 2)

        notification_id = Notification.objects.filter(user=self.student).first().id
        read_response = client.post(f"/api/v1/notifications/{notification_id}/read/")
        self.assertEqual(read_response.status_code, status.HTTP_200_OK)

        read_all_response = client.post("/api/v1/notifications/read-all/")
        self.assertEqual(read_all_response.status_code, status.HTTP_200_OK)
        self.assertEqual(read_all_response.data["data"]["marked_read"], 1)

        delete_response = client.delete(f"/api/v1/notifications/{notification_id}/")
        self.assertEqual(delete_response.status_code, status.HTTP_200_OK)
