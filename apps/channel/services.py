import logging
import re

from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django.urls import reverse

from apps.core.utils.sms import SendAfricaSmsClient as SendAfricaSmsClient
from apps.sms.services import SmsService

from .models import Channel, ChannelBroadcast, ChannelBroadcastDelivery, ChannelMember, ChannelWallet

logger = logging.getLogger('kibegi')


def normalize_phone_number(raw_phone: str) -> str | None:
    digits = re.sub(r"\D", "", raw_phone or "")
    if digits.startswith("255") and len(digits) == 12:
        national = digits[3:]
    elif digits.startswith("0") and len(digits) == 10:
        national = digits[1:]
    elif len(digits) == 9:
        national = digits
    else:
        return None

    if len(national) != 9 or national[0] not in {"6", "7"}:
        return None

    return f"+255{national}"


class ChannelService:
    @staticmethod
    def ensure_phone_verified(user):
        if not user or not user.is_authenticated:
            raise PermissionError("You need to sign in before using channel features.")
        if not getattr(user, 'phone_number', ''):
            raise ValueError("Please add a phone number to your Kibegi profile first.")
        if not getattr(user, 'phone_verified', False):
            raise ValueError("Please verify your phone number in your Kibegi profile first.")

    @staticmethod
    def get_wallet(channel: Channel):
        wallet, _ = ChannelWallet.objects.get_or_create(channel=channel)
        account = SmsService.get_account_for_owner(channel)

        sync_account_to_wallet = False
        sync_wallet_to_account = False

        if account.last_topup_at and (not wallet.last_topup_at or account.last_topup_at >= wallet.last_topup_at):
            sync_account_to_wallet = True
        elif wallet.last_topup_at and (not account.last_topup_at or wallet.last_topup_at > account.last_topup_at):
            sync_wallet_to_account = True
        elif account.balance_credits != wallet.balance_credits:
            if account.balance_credits > wallet.balance_credits:
                sync_account_to_wallet = True
            else:
                sync_wallet_to_account = True
        elif (
            account.provider_name != wallet.provider_name
            or account.sender_id != wallet.sender_id
            or account.is_active != wallet.is_active
        ):
            sync_account_to_wallet = True

        if sync_account_to_wallet:
            wallet.balance_credits = account.balance_credits
            wallet.provider_name = account.provider_name
            wallet.sender_id = account.sender_id
            wallet.is_active = account.is_active
            wallet.last_topup_reference = account.last_topup_reference
            wallet.last_topup_at = account.last_topup_at
            wallet.save(update_fields=['balance_credits', 'provider_name', 'sender_id', 'is_active', 'last_topup_reference', 'last_topup_at', 'updated_at'])

        if sync_wallet_to_account:
            account.balance_credits = wallet.balance_credits
            account.provider_name = wallet.provider_name
            account.sender_id = wallet.sender_id
            account.is_active = wallet.is_active
            account.last_topup_reference = wallet.last_topup_reference
            account.last_topup_at = wallet.last_topup_at
            account.save(update_fields=['balance_credits', 'provider_name', 'sender_id', 'is_active', 'last_topup_reference', 'last_topup_at', 'updated_at'])
        return wallet

    @staticmethod
    def user_can_manage(user, channel: Channel):
        if not user or not user.is_authenticated:
            return False
        if channel.created_by_id == user.id:
            return True
        membership = channel.memberships.filter(user=user, is_active=True).first()
        return bool(membership and membership.role in {ChannelMember.ROLE_OWNER, ChannelMember.ROLE_ADMIN})

    @staticmethod
    def build_urls(request, channel: Channel):
        info_url = request.build_absolute_uri(reverse('channel_public_info', kwargs={'invite_token': channel.invite_token}))
        join_url = request.build_absolute_uri(reverse('channel_public_join', kwargs={'invite_token': channel.invite_token}))
        return {
            'invite_token': channel.invite_token,
            'public_info_url': info_url,
            'public_join_url': join_url,
        }

    @staticmethod
    def build_message(broadcast: ChannelBroadcast):
        parts = ["Kibegi channel update"]
        if broadcast.subject:
            parts.append(broadcast.subject)
        if broadcast.venue:
            parts.append(f"Venue: {broadcast.venue}")
        parts.append(broadcast.message)
        return ' | '.join(part for part in parts if part)

    @staticmethod
    def resolve_member_phone(member: ChannelMember) -> str:
        phone = member.phone_number or getattr(member.user, 'phone_number', '') or ''
        normalized = normalize_phone_number(phone)
        return normalized or phone.strip()

    @staticmethod
    def resolve_user(identifier: str):
        from apps.authentication.models import User

        identifier = (identifier or '').strip()
        if not identifier:
            return None

        normalized_phone = normalize_phone_number(identifier)
        qs = User.objects.filter(is_active=True)
        if normalized_phone:
            return qs.filter(phone_number=normalized_phone).first()
        return qs.filter(
            Q(email__iexact=identifier) |
            Q(full_name__iexact=identifier) |
            Q(full_name__icontains=identifier)
        ).first()

    @classmethod
    def create_channel(cls, *, creator, name: str, description: str = '', visibility: str = Channel.VISIBILITY_PUBLIC):
        cls.ensure_phone_verified(creator)
        channel = Channel.objects.create(
            name=name.strip(),
            description=description.strip(),
            visibility=visibility,
            created_by=creator,
        )
        ChannelMember.objects.create(
            channel=channel,
            user=creator,
            role=ChannelMember.ROLE_OWNER,
            invited_by=creator,
        )
        cls.get_wallet(channel)
        return channel

    @classmethod
    def add_member(cls, channel: Channel, *, identifier: str, actor, role: str = ChannelMember.ROLE_MEMBER):
        if not cls.user_can_manage(actor, channel):
            raise PermissionError("You don't have permission to manage this channel.")

        user = cls.resolve_user(identifier)
        if not user:
            raise ValueError("Only registered Kibegi users can join a channel.")
        if not user.phone_number:
            raise ValueError("This user must add a phone number to receive channel SMS.")
        if not user.phone_verified:
            raise ValueError("This user must verify their phone number before joining the channel.")

        member, _ = ChannelMember.objects.update_or_create(
            channel=channel,
            user=user,
            defaults={
                'role': role,
                'display_name': user.full_name,
                'email': user.email,
                'phone_number': user.phone_number,
                'is_active': True,
                'left_at': None,
                'invited_by': actor,
            },
        )
        return member

    @classmethod
    def join_channel(cls, channel: Channel, user, invited_by=None):
        cls.ensure_phone_verified(user)

        existing = channel.memberships.filter(user=user).first()
        role = existing.role if existing and existing.role == ChannelMember.ROLE_OWNER else ChannelMember.ROLE_MEMBER
        member, created = ChannelMember.objects.update_or_create(
            channel=channel,
            user=user,
            defaults={
                'role': role,
                'display_name': user.full_name,
                'email': user.email,
                'phone_number': user.phone_number,
                'is_active': True,
                'left_at': None,
                'invited_by': invited_by,
            },
        )
        if not created and not member.is_active:
            member.is_active = True
            member.left_at = None
            member.save(update_fields=['is_active', 'left_at', 'updated_at'])
        return member

    @classmethod
    def dispatch_broadcast(cls, broadcast: ChannelBroadcast, client=None, now=None, dry_run=False):
        now = now or timezone.now()
        client = client or SendAfricaSmsClient()
        wallet = cls.get_wallet(broadcast.channel)
        message = cls.build_message(broadcast)
        account = SmsService.get_account_for_owner(broadcast.channel)
        account.balance_credits = wallet.balance_credits
        account.provider_name = wallet.provider_name
        account.sender_id = wallet.sender_id
        account.is_active = wallet.is_active
        account.save(update_fields=['balance_credits', 'provider_name', 'sender_id', 'is_active', 'updated_at'])

        members = list(
            ChannelMember.objects.filter(
                channel=broadcast.channel,
                is_active=True,
                user__is_active=True,
            ).select_related('user').order_by('display_name')
        )
        deliverable_members = []
        for member in members:
            recipient_phone = cls.resolve_member_phone(member)
            if recipient_phone:
                deliverable_members.append((member, recipient_phone))

        broadcast.status = ChannelBroadcast.STATUS_SENDING
        broadcast.recipient_count = len(deliverable_members)
        broadcast.sent_count = 0
        broadcast.failed_count = 0
        broadcast.skipped_count = 0
        broadcast.credits_used = 0
        broadcast.save(update_fields=['status', 'recipient_count', 'sent_count', 'failed_count', 'skipped_count', 'credits_used', 'updated_at'])

        if not deliverable_members:
            broadcast.status = ChannelBroadcast.STATUS_FAILED
            broadcast.failed_count = 0
            broadcast.skipped_count = len(members)
            broadcast.save(update_fields=['status', 'updated_at'])
            return broadcast

        if not wallet.is_active:
            for member, recipient_phone in deliverable_members:
                ChannelBroadcastDelivery.objects.create(
                    broadcast=broadcast,
                    member=member,
                    recipient_phone=recipient_phone,
                    provider_name=wallet.provider_name,
                    status=ChannelBroadcastDelivery.STATUS_SKIPPED,
                    message=message,
                    credits_used=0,
                    error_message='SMS wallet is inactive.',
                    sent_at=now,
                )
            broadcast.status = ChannelBroadcast.STATUS_FAILED
            broadcast.skipped_count = len(members)
            broadcast.save(update_fields=['status', 'skipped_count', 'updated_at'])
            return broadcast

        cost_per_message = getattr(settings, 'CHANNEL_SMS_COST_PER_MESSAGE', 1)
        provider_manages_balance = getattr(settings, 'SMS_PROVIDER_MANAGES_BALANCE', True)
        sent_count = failed_count = skipped_count = credits_used = 0

        for member, recipient_phone in deliverable_members:
            if not provider_manages_balance and account.balance_credits < cost_per_message:
                ChannelBroadcastDelivery.objects.create(
                    broadcast=broadcast,
                    member=member,
                    recipient_phone=recipient_phone,
                    provider_name=wallet.provider_name,
                    status=ChannelBroadcastDelivery.STATUS_SKIPPED,
                    message=message,
                    credits_used=0,
                    error_message='Insufficient SMS credits.',
                    sent_at=now,
                )
                skipped_count += 1
                continue

            if dry_run:
                ChannelBroadcastDelivery.objects.create(
                    broadcast=broadcast,
                    member=member,
                    recipient_phone=recipient_phone,
                    provider_name=wallet.provider_name,
                    status=ChannelBroadcastDelivery.STATUS_PENDING,
                    message=message,
                    credits_used=cost_per_message,
                    sent_at=None,
                )
                sent_count += 1
                credits_used += cost_per_message
                account.balance_credits = max(0, account.balance_credits - cost_per_message)
                continue

            try:
                delivery = SmsService.send_single(
                    account=account,
                    phone_number=recipient_phone,
                    message=message,
                    context=broadcast,
                    dry_run=False,
                    cost=cost_per_message,
                    client=client,
                )
            except Exception as exc:
                ChannelBroadcastDelivery.objects.create(
                    broadcast=broadcast,
                    member=member,
                    recipient_phone=recipient_phone,
                    provider_name=wallet.provider_name,
                    status=ChannelBroadcastDelivery.STATUS_FAILED,
                    message=message,
                    credits_used=0,
                    error_message=str(exc),
                    sent_at=now,
                )
                failed_count += 1
                continue

            ChannelBroadcastDelivery.objects.create(
                broadcast=broadcast,
                member=member,
                recipient_phone=recipient_phone,
                provider_name=delivery.provider_name,
                provider_message_id=delivery.provider_message_id,
                status=delivery.status,
                message=message,
                credits_used=delivery.credits_used,
                error_message=delivery.error_message,
                provider_response=delivery.provider_response,
                sent_at=delivery.sent_at,
            )

            if delivery.status == 'sent':
                sent_count += 1
                credits_used += delivery.credits_used
            elif delivery.status == 'failed':
                failed_count += 1
            else:
                skipped_count += 1

            account.refresh_from_db()

        wallet.balance_credits = account.balance_credits
        wallet.provider_name = account.provider_name
        wallet.sender_id = account.sender_id
        wallet.is_active = account.is_active
        wallet.save(update_fields=['balance_credits', 'provider_name', 'sender_id', 'is_active', 'updated_at'])

        if sent_count and failed_count:
            status = ChannelBroadcast.STATUS_PARTIAL
        elif sent_count:
            status = ChannelBroadcast.STATUS_SENT
        else:
            status = ChannelBroadcast.STATUS_FAILED

        broadcast.status = status
        broadcast.sent_count = sent_count
        broadcast.failed_count = failed_count
        broadcast.skipped_count = skipped_count
        broadcast.credits_used = credits_used
        broadcast.sent_at = now if sent_count else None
        broadcast.save(update_fields=['status', 'sent_count', 'failed_count', 'skipped_count', 'credits_used', 'sent_at', 'updated_at'])
        return broadcast
