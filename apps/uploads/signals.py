from django.db.models.signals import post_save
from django.dispatch import receiver


def _notify(sender, instance, created, **kwargs):
    if not created:
        return
    from apps.notifications.services import ClassUpdateNotifier
    ClassUpdateNotifier.notify_new_upload(instance)


def connect():
    from .models import Upload
    post_save.connect(_notify, sender=Upload, dispatch_uid='uploads.notify_class_on_upload')
