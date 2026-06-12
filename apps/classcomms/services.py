import logging
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.urls import reverse

from apps.sms.services import SmsService
from apps.core.utils.sms import SendAfricaSmsClient as AfricasTalkingSmsClient
from apps.classes.models import Class, Membership

from .models import ClassBroadcast, ClassBroadcastDelivery, ClassCommsProfile, ClassCommsWallet, ClassContact

logger = logging.getLogger('kibegi')


class ClassCommsService:
    """Business logic for class contact management and SMS broadcasts."""

    @staticmethod
    def get_profile_for_class(class_obj: Class):
        """Return the class comms profile, creating a default record if needed."""
        profile, _ = ClassCommsProfile.objects.get_or_create(class_obj=class_obj)
        return profile

    @staticmethod
    def get_wallet_for_class(class_obj: Class):
        """Return the class SMS wallet, creating a default record if needed."""
        wallet, _ = ClassCommsWallet.objects.get_or_create(class_obj=class_obj)
        return wallet

    @staticmethod
    def user_can_manage_class_comms(user, class_obj: Class):
        """Check whether the user may manage class communications."""
        if not user or not user.is_authenticated:
            return False
        if class_obj.creator_id == user.id:
            return True
        membership = class_obj.memberships.filter(user=user).only('role').first()
        return bool(membership and membership.role in {'lecturer', 'representative'})

    @classmethod
    def build_registration_urls(cls, request, class_obj: Class):
        """Build the public URLs the frontend needs for contact registration."""
        profile = cls.get_profile_for_class(class_obj)
        info_url = request.build_absolute_uri(
            reverse('classcomms_public_info', kwargs={'public_token': profile.public_token})
        )
        register_url = request.build_absolute_uri(
            reverse('classcomms_public_register', kwargs={'public_token': profile.public_token})
        )
        return {
            'public_token': profile.public_token,
            'public_info_url': info_url,
            'public_register_url': register_url,
        }

    @staticmethod
    def build_broadcast_message(broadcast: ClassBroadcast):
        """Join subject, venue, and message into one SMS-friendly body."""
        parts = ["Kibegi class update"]
        if broadcast.subject:
            parts.append(broadcast.subject)
        if broadcast.venue:
            parts.append(f"Venue: {broadcast.venue}")
        parts.append(broadcast.message)
        return ' | '.join(part for part in parts if part)

    @staticmethod
    def upsert_contact(class_obj: Class, *, full_name: str, phone_number: str, consent_granted=True, consent_source=ClassContact.SOURCE_MANUAL, notes='', registered_by=None, created_by=None):
        """Create a new contact or refresh an existing one for the same phone number."""
        defaults = {
            'full_name': full_name.strip(),
            'consent_granted': consent_granted,
            'consent_source': consent_source,
            'notes': notes,
            'registered_by': registered_by,
            'created_by': created_by,
            'verified_at': timezone.now() if consent_granted else None,
            'is_active': True,
        }
        contact, created = ClassContact.objects.update_or_create(
            class_obj=class_obj,
            phone_number=phone_number.strip(),
            defaults=defaults,
        )
        if not created and contact.consent_granted != consent_granted:
            contact.consent_granted = consent_granted
            contact.verified_at = timezone.now() if consent_granted else None
            contact.save(update_fields=['consent_granted', 'verified_at', 'updated_at'])
        return contact, created

    @classmethod
    def promote_member_to_representative(cls, class_obj: Class, user, actor):
        """Change an existing membership role to representative."""
        if not cls.user_can_manage_class_comms(actor, class_obj):
            raise PermissionError("You don't have permission to manage class representatives.")

        membership = class_obj.memberships.filter(user=user).first()
        if not membership:
            raise LookupError("The selected user is not a member of this class.")

        membership.role = 'representative'
        membership.save(update_fields=['role'])
        return membership

    @classmethod
    def dispatch_broadcast(cls, broadcast: ClassBroadcast, client=None, now=None, dry_run=False):
        """Send a broadcast to all consented, active contacts in the class."""
        now = now or timezone.now()
        client = client or AfricasTalkingSmsClient()
        wallet = cls.get_wallet_for_class(broadcast.class_obj)
        message = cls.build_broadcast_message(broadcast)
        central_account = SmsService.get_account_for_owner(broadcast.class_obj)
        contacts = list(
            ClassContact.objects.filter(class_obj=broadcast.class_obj, is_active=True, consent_granted=True).order_by('full_name')
        )

        broadcast.status = ClassBroadcast.STATUS_SENDING
        broadcast.recipient_count = len(contacts)
        broadcast.sent_count = 0
        broadcast.failed_count = 0
        broadcast.skipped_count = 0
        broadcast.credits_used = 0
        broadcast.save(update_fields=['status', 'recipient_count', 'sent_count', 'failed_count', 'skipped_count', 'credits_used', 'updated_at'])

        if not contacts:
            broadcast.status = ClassBroadcast.STATUS_FAILED
            broadcast.save(update_fields=['status', 'updated_at'])
            return broadcast

        if not wallet.is_active:
            for contact in contacts:
                ClassBroadcastDelivery.objects.create(
                    broadcast=broadcast,
                    contact=contact,
                    recipient_phone=contact.phone_number,
                    provider_name=wallet.provider_name,
                    status=ClassBroadcastDelivery.STATUS_SKIPPED,
                    message=message,
                    credits_used=0,
                    error_message='SMS wallet is inactive.',
                    sent_at=now,
                )
            broadcast.status = ClassBroadcast.STATUS_FAILED
            broadcast.skipped_count = len(contacts)
            broadcast.save(update_fields=['status', 'skipped_count', 'updated_at'])
            return broadcast

        cost_per_message = getattr(settings, 'CLASS_COMMS_SMS_COST_PER_MESSAGE', 1)
        sent_count = 0
        failed_count = 0
        skipped_count = 0
        credits_used = 0

        # prefer legacy wallet's balance if central account is empty
        try:
            legacy_wallet = ClassCommsWallet.objects.get(class_obj=broadcast.class_obj)
        except ClassCommsWallet.DoesNotExist:
            legacy_wallet = None

        for contact in contacts:
            # if legacy wallet indicates insufficient funds, skip early
            if legacy_wallet and legacy_wallet.balance_credits < cost_per_message:
                ClassBroadcastDelivery.objects.create(
                    broadcast=broadcast,
                    contact=contact,
                    recipient_phone=contact.phone_number,
                    provider_name=legacy_wallet.provider_name,
                    status=ClassBroadcastDelivery.STATUS_SKIPPED,
                    message=message,
                    credits_used=0,
                    error_message='Insufficient SMS credits.',
                    sent_at=now,
                )
                skipped_count += 1
                continue

            if dry_run:
                ClassBroadcastDelivery.objects.create(
                    broadcast=broadcast,
                    contact=contact,
                    recipient_phone=contact.phone_number,
                    provider_name=legacy_wallet.provider_name if legacy_wallet else central_account.provider_name,
                    status=ClassBroadcastDelivery.STATUS_PENDING,
                    message=message,
                    credits_used=cost_per_message,
                    sent_at=None,
                )
                sent_count += 1
                credits_used += cost_per_message
                continue

            # ensure central account has funds mirrored from legacy wallet if needed
            if legacy_wallet and central_account.balance_credits < cost_per_message and legacy_wallet.balance_credits >= cost_per_message:
                central_account.balance_credits = legacy_wallet.balance_credits
                central_account.phone_number = legacy_wallet.sender_id or central_account.phone_number
                central_account.sender_id = legacy_wallet.sender_id or central_account.sender_id
                central_account.provider_name = legacy_wallet.provider_name or central_account.provider_name
                central_account.save(update_fields=['balance_credits', 'phone_number', 'sender_id', 'provider_name', 'updated_at'])

            try:
                delivery = SmsService.send_single(account=central_account, phone_number=contact.phone_number, message=message, context=broadcast, dry_run=dry_run, cost=cost_per_message, client=client)
            except Exception as exc:
                ClassBroadcastDelivery.objects.create(
                    broadcast=broadcast,
                    contact=contact,
                    recipient_phone=contact.phone_number,
                    provider_name=central_account.provider_name,
                    status=ClassBroadcastDelivery.STATUS_FAILED,
                    message=message,
                    credits_used=0,
                    error_message=str(exc),
                    sent_at=now,
                )
                failed_count += 1
                continue

            # refresh central account balance and sync to legacy wallet
            try:
                central_account.refresh_from_db()
            except Exception:
                pass

            if legacy_wallet:
                try:
                    legacy_wallet.balance_credits = central_account.balance_credits
                    legacy_wallet.save(update_fields=['balance_credits', 'updated_at'])
                except Exception:
                    pass

            # persist the delivery record in the classcomms table
            ClassBroadcastDelivery.objects.create(
                broadcast=broadcast,
                contact=contact,
                recipient_phone=delivery.recipient_phone,
                provider_name=delivery.provider_name,
                provider_message_id=getattr(delivery, 'provider_message_id', '') or delivery.provider_message_id,
                status=delivery.status,
                message=delivery.message,
                credits_used=delivery.credits_used,
                provider_response=delivery.provider_response,
                error_message=delivery.error_message,
                sent_at=delivery.sent_at,
            )

            if delivery.status == ClassBroadcastDelivery.STATUS_SENT:
                sent_count += 1
                credits_used += delivery.credits_used
            elif delivery.status == ClassBroadcastDelivery.STATUS_FAILED:
                failed_count += 1
            else:
                skipped_count += 1

        if sent_count and (failed_count or skipped_count):
            status = ClassBroadcast.STATUS_PARTIAL
        elif sent_count:
            status = ClassBroadcast.STATUS_SENT
        else:
            status = ClassBroadcast.STATUS_FAILED

        broadcast.status = status
        broadcast.sent_count = sent_count
        broadcast.failed_count = failed_count
        broadcast.skipped_count = skipped_count
        broadcast.credits_used = credits_used
        broadcast.sent_at = now if sent_count else None
        broadcast.save(update_fields=['status', 'sent_count', 'failed_count', 'skipped_count', 'credits_used', 'sent_at', 'updated_at'])
        return broadcast
