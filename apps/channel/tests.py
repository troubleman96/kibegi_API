from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.sms.services import SmsService

from .models import Channel, ChannelBroadcast, ChannelMember
from .services import ChannelService

User = get_user_model()


@override_settings(ALLOWED_HOSTS=['testserver'])
class ChannelAPITests(TestCase):
    def setUp(self):
        self.creator = User.objects.create_user(
            email='creator@kibegi.test',
            password='StrongPass123!',
            full_name='Campaign Owner',
            user_type='lecturer',
            phone_number='+255700000001',
            phone_verified=True,
        )
        self.member = User.objects.create_user(
            email='member@kibegi.test',
            password='StrongPass123!',
            full_name='Channel Member',
            user_type='student',
            phone_number='+255700000002',
            phone_verified=True,
        )
        self.client = APIClient()
        self.client.force_authenticate(self.creator)
        self.channel = ChannelService.create_channel(
            creator=self.creator,
            name='Exam Updates',
            description='Broadcast channel for exam announcements',
            visibility=Channel.VISIBILITY_PUBLIC,
        )
        wallet = ChannelService.get_wallet(self.channel)
        wallet.balance_credits = 5
        wallet.save(update_fields=['balance_credits', 'updated_at'])

    def _zero_local_ledger(self):
        """Drain both the channel wallet and the underlying SmsAccount so the
        two-way sync in get_wallet cannot restore a non-zero balance."""
        wallet = ChannelService.get_wallet(self.channel)
        wallet.balance_credits = 0
        wallet.save(update_fields=['balance_credits', 'updated_at'])
        account = SmsService.get_account_for_owner(self.channel)
        account.balance_credits = 0
        account.save(update_fields=['balance_credits', 'updated_at'])

    def test_creator_can_create_channel(self):
        response = self.client.post(
            reverse('channel_list_create'),
            {'name': 'Freshers Updates', 'description': 'New student channel', 'visibility': 'private'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(Channel.objects.filter(name='Freshers Updates').exists())

    def test_unverified_user_cannot_create_channel(self):
        unverified = User.objects.create_user(
            email='unverified@kibegi.test',
            password='StrongPass123!',
            full_name='Unverified User',
            user_type='student',
            phone_number='+255700000099',
            phone_verified=False,
        )
        self.client.force_authenticate(unverified)
        response = self.client.post(
            reverse('channel_list_create'),
            {'name': 'Blocked Channel', 'description': 'Should not be created', 'visibility': 'public'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn('verify your phone number', response.data['message'].lower())

    def test_member_can_join_public_channel(self):
        self.client.force_authenticate(self.member)
        response = self.client.post(reverse('channel_join', kwargs={'channel_id': self.channel.pk}))

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(ChannelMember.objects.filter(channel=self.channel, user=self.member, is_active=True).exists())

    def test_creator_can_add_member_by_email(self):
        response = self.client.post(
            reverse('channel_members', kwargs={'channel_id': self.channel.pk}),
            {'identifier': self.member.email, 'role': 'member'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(ChannelMember.objects.filter(channel=self.channel, user=self.member, is_active=True).exists())

    def test_channel_wallet_syncs_from_sms_account_topup(self):
        account = SmsService.get_account_for_owner(self.channel)
        account.balance_credits = 8
        account.last_topup_at = timezone.now()
        account.save(update_fields=['balance_credits', 'last_topup_at', 'updated_at'])

        wallet = ChannelService.get_wallet(self.channel)
        wallet.refresh_from_db()

        self.assertEqual(wallet.balance_credits, 8)
        self.assertEqual(wallet.last_topup_at, account.last_topup_at)

    @patch('apps.core.utils.sms.SendAfricaSmsClient.send_sms')
    def test_broadcast_sends_sms_and_deducts_credits(self, mock_send_sms):
        mock_send_sms.return_value = {
            'provider_message_id': 'msg-1',
            'raw_response': {'ok': True},
        }
        recipient = User.objects.create_user(
            email='recipient@kibegi.test',
            password='StrongPass123!',
            full_name='Venue Recipient',
            user_type='student',
            phone_number='+255628587749',
            phone_verified=True,
        )
        ChannelService.add_member(self.channel, identifier=recipient.email, actor=self.creator)

        response = self.client.post(
            reverse('channel_broadcasts', kwargs={'channel_id': self.channel.pk}),
            {'subject': 'Venue update', 'message': 'Lecture moved to the new room.', 'venue': 'Mezzanie'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        broadcast = ChannelBroadcast.objects.get(pk=response.data['data']['id'])
        self.assertEqual(broadcast.status, ChannelBroadcast.STATUS_SENT)
        self.assertEqual(broadcast.sent_count, 2)
        self.assertEqual(broadcast.credits_used, 2)
        account = SmsService.get_account_for_owner(self.channel)
        self.assertEqual(account.balance_credits, 3)
        self.assertEqual(broadcast.deliveries.count(), 2)
        self.assertEqual(mock_send_sms.call_count, 2)
        expected_message = 'Kibegi channel update | Venue update | Venue: Mezzanie | Lecture moved to the new room.'
        mock_send_sms.assert_any_call(phone_number='+255628587749', message=expected_message, sender_id='')
        self.assertIn('Venue: Mezzanie', expected_message)

    @patch('apps.core.utils.sms.SendAfricaSmsClient.send_sms')
    def test_broadcast_uses_registered_user_phone_when_membership_phone_missing(self, mock_send_sms):
        mock_send_sms.return_value = {
            'provider_message_id': 'msg-1',
            'raw_response': {'ok': True},
        }
        recipient = User.objects.create_user(
            email='fallback@kibegi.test',
            password='StrongPass123!',
            full_name='Fallback Member',
            user_type='student',
            phone_number='+255628587749',
            phone_verified=True,
        )
        ChannelService.add_member(self.channel, identifier=recipient.email, actor=self.creator)
        member = ChannelMember.objects.get(channel=self.channel, user=recipient)
        member.phone_number = ''
        member.save(update_fields=['phone_number', 'updated_at'])

        response = self.client.post(
            reverse('channel_broadcasts', kwargs={'channel_id': self.channel.pk}),
            {'subject': 'Venue update', 'message': 'Room moved.', 'venue': 'Mezzanie'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(mock_send_sms.called)
        self.assertTrue(any(call.kwargs['phone_number'] == '+255628587749' for call in mock_send_sms.call_args_list))
        broadcast = ChannelBroadcast.objects.get(pk=response.data['data']['id'])
        self.assertEqual(broadcast.deliveries.first().recipient_phone, '+255628587749')

    @override_settings(SMS_PROVIDER_MANAGES_BALANCE=True)
    @patch('apps.core.utils.sms.SendAfricaSmsClient.send_sms')
    def test_broadcast_sends_when_provider_manages_balance_despite_low_local_ledger(self, mock_send_sms):
        """SendAfrica is the source of truth for balance, so a low/zero local
        ledger must not skip recipients with 'Insufficient SMS credits.'"""
        mock_send_sms.return_value = {
            'provider_message_id': 'msg-1',
            'raw_response': {'ok': True},
        }
        recipient = User.objects.create_user(
            email='provider-balance@kibegi.test',
            password='StrongPass123!',
            full_name='Provider Balance Member',
            user_type='student',
            phone_number='+255628587749',
            phone_verified=True,
        )
        ChannelService.add_member(self.channel, identifier=recipient.email, actor=self.creator)

        # Local ledger has zero credits, but SendAfrica has real balance.
        self._zero_local_ledger()

        response = self.client.post(
            reverse('channel_broadcasts', kwargs={'channel_id': self.channel.pk}),
            {'subject': 'Exam', 'message': 'Exam starts at 9am.'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        broadcast = ChannelBroadcast.objects.get(pk=response.data['data']['id'])
        self.assertEqual(broadcast.status, ChannelBroadcast.STATUS_SENT)
        self.assertEqual(broadcast.sent_count, 2)
        self.assertEqual(broadcast.skipped_count, 0)
        self.assertFalse(
            broadcast.deliveries.filter(error_message='Insufficient SMS credits.').exists()
        )
        # Ledger clamps at zero rather than going negative.
        account = SmsService.get_account_for_owner(self.channel)
        self.assertEqual(account.balance_credits, 0)

    @override_settings(SMS_PROVIDER_MANAGES_BALANCE=False)
    @patch('apps.core.utils.sms.SendAfricaSmsClient.send_sms')
    def test_broadcast_skips_when_local_ledger_enforced_and_empty(self, mock_send_sms):
        """With the local prepaid ledger enforced, a zero balance still skips."""
        mock_send_sms.return_value = {
            'provider_message_id': 'msg-1',
            'raw_response': {'ok': True},
        }
        recipient = User.objects.create_user(
            email='enforced-balance@kibegi.test',
            password='StrongPass123!',
            full_name='Enforced Balance Member',
            user_type='student',
            phone_number='+255628587749',
            phone_verified=True,
        )
        ChannelService.add_member(self.channel, identifier=recipient.email, actor=self.creator)

        self._zero_local_ledger()

        response = self.client.post(
            reverse('channel_broadcasts', kwargs={'channel_id': self.channel.pk}),
            {'subject': 'Exam', 'message': 'Exam starts at 9am.'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        broadcast = ChannelBroadcast.objects.get(pk=response.data['data']['id'])
        self.assertEqual(broadcast.sent_count, 0)
        self.assertTrue(
            broadcast.deliveries.filter(error_message='Insufficient SMS credits.').exists()
        )
        self.assertFalse(mock_send_sms.called)
