from django.db.models.signals import post_save
from django.dispatch import receiver


def _trigger_ai_processing(sender, instance, created, **kwargs):
    if not created:
        return
    from .processing import should_process, process_upload_async
    if should_process(instance):
        process_upload_async(str(instance.pk))


def connect():
    from apps.uploads.models import Upload
    post_save.connect(
        _trigger_ai_processing,
        sender=Upload,
        dispatch_uid='ai.process_upload_on_create',
    )
