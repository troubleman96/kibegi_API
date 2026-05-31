from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.urls import reverse
from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.test import APIClient

from apps.classes.models import Class, Membership

from .models import ClassBroadcast, ClassCommsWallet, ClassContact
from .services import ClassCommsService

User = get_user_model()


@override_settings(ALLOWED_HOSTS=['testserver'])
class ClassCommsAPITests(TestCase):
    def setUp(self):
        self.creator = User.objects.create_user(
            email='lecturer@classcomms.test',
            password='StrongPass123!',
            full_name='Lead Lecturer',
            user_type='lecturer',
        )
        self.representative = User.objects.create_user(
            email='rep@classcomms.test',
            password='StrongPass123!',
            full_name='Class Rep',
            user_type='student',
        )
        self.other_student = User.objects.create_user(
            email='student@classcomms.test',
            password='StrongPass123!',
            full_name='Other Student',
            user_type='student',
        )

        self.class_obj = Class.objects.create(
            name='Software Engineering',
            description='Communication test class',
            creator=self.creator,
            is_public=True,
            is_verified=True,
        )
        Membership.objects.create(user=self.creator, class_obj=self.class_obj, role='lecturer')
        self.rep_membership = Membership.objects.create(user=self.representative, class_obj=self.class_obj, role='student')
        Membership.objects.create(user=self.other_student, class_obj=self.class_obj, role='student')

        self.client = APIClient()
        self.public_client = APIClient()

        self.profile = ClassCommsService.get_profile_for_class(self.class_obj)
        self.wallet = ClassCommsService.get_wallet_for_class(self.class_obj)
        self.wallet.balance_credits = 10
        self.wallet.save(update_fields=['balance_credits', 'updated_at'])

    def promote_representative(self):
        self.client.force_authenticate(self.creator)
        response = self.client.post(
            reverse('classcomms_representatives', kwargs={'class_id': self.class_obj.pk}),
            {'user_id': str(self.representative.id), 'role': 'representative'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.rep_membership.refresh_from_db()
        self.assertEqual(self.rep_membership.role, 'representative')

    def test_creator_can_promote_member_to_representative(self):
        self.promote_representative()

    def test_representative_can_add_contact(self):
        self.promote_representative()
        self.client.force_authenticate(self.representative)

        response = self.client.post(
            reverse('classcomms_contacts', kwargs={'class_id': self.class_obj.pk}),
            {
                'full_name': 'Alice Student',
                'phone_number': '+255700000001',
                'consent_granted': True,
                'notes': 'Prefers SMS updates',
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(ClassContact.objects.filter(class_obj=self.class_obj, phone_number='+255700000001').exists())

    def test_public_registration_creates_contact(self):
        response = self.public_client.post(
            reverse('classcomms_public_register', kwargs={'public_token': self.profile.public_token}),
            {
                'full_name': 'Public Registrant',
                'phone_number': '+255700000002',
                'consent_granted': True,
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        contact = ClassContact.objects.get(class_obj=self.class_obj, phone_number='+255700000002')
        self.assertEqual(contact.consent_source, ClassContact.SOURCE_PUBLIC)
        self.assertEqual(contact.full_name, 'Public Registrant')

    @patch('apps.classcomms.services.AfricasTalkingSmsClient.send_sms')
    def test_broadcast_sends_sms_and_deducts_credits(self, mock_send_sms):
        mock_send_sms.side_effect = [
            {'provider_message_id': 'msg-1', 'raw_response': {'ok': True}},
            {'provider_message_id': 'msg-2', 'raw_response': {'ok': True}},
        ]
        ClassCommsService.upsert_contact(
            self.class_obj,
            full_name='Alice Student',
            phone_number='+255700000003',
            consent_granted=True,
            consent_source=ClassContact.SOURCE_MANUAL,
            registered_by=self.creator,
            created_by=self.creator,
        )
        ClassCommsService.upsert_contact(
            self.class_obj,
            full_name='Bob Student',
            phone_number='+255700000004',
            consent_granted=True,
            consent_source=ClassContact.SOURCE_MANUAL,
            registered_by=self.creator,
            created_by=self.creator,
        )
        self.wallet.balance_credits = 2
        self.wallet.save(update_fields=['balance_credits', 'updated_at'])

        self.promote_representative()
        self.client.force_authenticate(self.representative)

        response = self.client.post(
            reverse('classcomms_broadcasts', kwargs={'class_id': self.class_obj.pk}),
            {
                'subject': 'Venue update',
                'message': 'Class has moved to the main hall at 2 PM.',
                'venue': 'Main Hall',
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        broadcast = ClassBroadcast.objects.get(pk=response.data['data']['id'])
        broadcast.refresh_from_db()
        self.wallet.refresh_from_db()
        self.assertEqual(broadcast.status, ClassBroadcast.STATUS_SENT)
        self.assertEqual(broadcast.sent_count, 2)
        self.assertEqual(broadcast.credits_used, 2)
        self.assertEqual(self.wallet.balance_credits, 0)
        self.assertEqual(broadcast.deliveries.count(), 2)
        self.assertEqual(mock_send_sms.call_count, 2)
