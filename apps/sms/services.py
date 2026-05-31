import logging
from typing import Iterable, List
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.utils import timezone
from django.conf import settings

from apps.core.utils.sms import AfricasTalkingSmsClient
from .models import SmsAccount, SmsDelivery

logger = logging.getLogger('kibegi')


class SmsService:
    """Central SMS operations: account lookup, single/bulk send, and accounting."""

    @staticmethod
    def get_account_for_owner(owner):
        """Get or create an SmsAccount tied to a Django model instance (user, class, etc.)."""
        owner_ct = ContentType.objects.get_for_model(owner.__class__)
        obj_id = str(getattr(owner, 'id', owner))
        account, _ = SmsAccount.objects.get_or_create(
            owner_content_type=owner_ct,
            owner_object_id=obj_id,
            defaults={'phone_number': getattr(owner, 'phone_number', '')}
        )
        return account

    @staticmethod
    def build_message(subject: str, body: str, venue: str = '') -> str:
        parts = []
        if subject:
            parts.append(subject)
        if venue:
            parts.append(f"Venue: {venue}")
        if body:
            parts.append(body)
        prefix = getattr(settings, 'SMS_MESSAGE_PREFIX', 'Kibegi')
        return ' | '.join([prefix] + [p for p in parts if p])

    @classmethod
    def send_single(cls, account: SmsAccount, phone_number: str, message: str, context=None, dry_run=False, cost=1, client=None):
        now = timezone.now()
        client = client or AfricasTalkingSmsClient()

        if not account.is_active:
            return SmsDelivery.objects.create(
                context_content_type=ContentType.objects.get_for_model(context.__class__) if context is not None else ContentType.objects.get_for_model(account.owner.__class__),
                context_object_id=str(getattr(context, 'id', '')), 
                sms_account=account,
                recipient_phone=phone_number,
                provider_name=account.provider_name,
                status=SmsDelivery.STATUS_SKIPPED,
                message=message,
                credits_used=0,
                error_message='SMS account is inactive.',
                sent_at=now,
            )

        if account.balance_credits < cost:
            return SmsDelivery.objects.create(
                context_content_type=ContentType.objects.get_for_model(context.__class__) if context is not None else ContentType.objects.get_for_model(account.owner.__class__),
                context_object_id=str(getattr(context, 'id', '')),
                sms_account=account,
                recipient_phone=phone_number,
                provider_name=account.provider_name,
                status=SmsDelivery.STATUS_SKIPPED,
                message=message,
                credits_used=0,
                error_message='Insufficient SMS credits.',
                sent_at=now,
            )

        if dry_run:
            return SmsDelivery.objects.create(
                context_content_type=ContentType.objects.get_for_model(context.__class__) if context is not None else ContentType.objects.get_for_model(account.owner.__class__),
                context_object_id=str(getattr(context, 'id', '')),
                sms_account=account,
                recipient_phone=phone_number,
                provider_name=account.provider_name,
                status=SmsDelivery.STATUS_PENDING,
                message=message,
                credits_used=cost,
                sent_at=None,
            )

        try:
            provider_result = client.send_sms(phone_number=phone_number, message=message, sender_id=account.sender_id)
        except Exception as exc:
            return SmsDelivery.objects.create(
                context_content_type=ContentType.objects.get_for_model(context.__class__) if context is not None else ContentType.objects.get_for_model(account.owner.__class__),
                context_object_id=str(getattr(context, 'id', '')),
                sms_account=account,
                recipient_phone=phone_number,
                provider_name=account.provider_name,
                status=SmsDelivery.STATUS_FAILED,
                message=message,
                credits_used=0,
                error_message=str(exc),
                sent_at=now,
            )

        with transaction.atomic():
            locked = SmsAccount.objects.select_for_update().get(pk=account.pk)
            if locked.balance_credits < cost:
                return SmsDelivery.objects.create(
                    context_content_type=ContentType.objects.get_for_model(context.__class__) if context is not None else ContentType.objects.get_for_model(account.owner.__class__),
                    context_object_id=str(getattr(context, 'id', '')),
                    sms_account=account,
                    recipient_phone=phone_number,
                    provider_name=account.provider_name,
                    status=SmsDelivery.STATUS_SKIPPED,
                    message=message,
                    credits_used=0,
                    error_message='Insufficient SMS credits.',
                    sent_at=now,
                )
            locked.balance_credits -= cost
            locked.save(update_fields=['balance_credits', 'updated_at'])
            return SmsDelivery.objects.create(
                context_content_type=ContentType.objects.get_for_model(context.__class__) if context is not None else ContentType.objects.get_for_model(account.owner.__class__),
                context_object_id=str(getattr(context, 'id', '')),
                sms_account=locked,
                recipient_phone=phone_number,
                provider_name=locked.provider_name,
                provider_message_id=provider_result.get('provider_message_id', ''),
                status=SmsDelivery.STATUS_SENT,
                message=message,
                credits_used=cost,
                provider_response=provider_result.get('raw_response'),
                sent_at=now,
            )

    @classmethod
    def send_bulk(cls, owner, recipients: Iterable[str], message: str, context=None, dry_run=False, cost_per_message=None):
        """Send to a sequence of phone numbers, deducting credits per successful send.

        Returns summary dict and list of created SmsDelivery objects.
        """
        account = cls.get_account_for_owner(owner)
        cost = cost_per_message or getattr(settings, 'CLASS_COMMS_SMS_COST_PER_MESSAGE', 1)
        results = []
        sent = failed = skipped = 0
        credits_used = 0
        for phone in recipients:
            delivery = cls.send_single(account, phone, message, context=context, dry_run=dry_run, cost=cost)
            results.append(delivery)
            if delivery.status == SmsDelivery.STATUS_SENT:
                sent += 1
                credits_used += delivery.credits_used
            elif delivery.status == SmsDelivery.STATUS_FAILED:
                failed += 1
            else:
                skipped += 1
        summary = {
            'sent': sent,
            'failed': failed,
            'skipped': skipped,
            'credits_used': credits_used,
            'total': len(list(recipients)),
        }
        return summary, results
