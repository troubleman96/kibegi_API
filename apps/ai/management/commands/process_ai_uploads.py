from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.ai.models import AIProcessingJob
from apps.ai.processing import STALE_PROCESSING_AFTER, _process_upload, should_process
from apps.uploads.models import Upload


class Command(BaseCommand):
    help = "Process or retry uploads that can be indexed for Kibegi AI."

    def add_arguments(self, parser):
        parser.add_argument(
            "--upload-id",
            help="Process a single upload UUID.",
        )
        parser.add_argument(
            "--retry-stuck",
            action="store_true",
            help="Retry jobs stuck in processing longer than the stale threshold.",
        )
        parser.add_argument(
            "--failed",
            action="store_true",
            help="Retry failed jobs.",
        )
        parser.add_argument(
            "--all",
            action="store_true",
            help="Process every supported upload, including ones with completed jobs.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=100,
            help="Maximum uploads to process. Default: 100.",
        )

    def handle(self, *args, **options):
        upload_id = options.get("upload_id")
        if upload_id:
            uploads = Upload.objects.filter(id=upload_id, is_deleted=False)
        else:
            uploads = Upload.objects.filter(is_deleted=False).order_by("created_at")

        supported = [upload for upload in uploads if should_process(upload)]
        if not options["all"]:
            supported = [upload for upload in supported if self._needs_processing(upload, options)]

        limit = options["limit"]
        selected = supported[:limit]
        for upload in selected:
            self.stdout.write(f"Processing {upload.id} {upload.file_name}")
            _process_upload(str(upload.id))

        self.stdout.write(self.style.SUCCESS(f"Processed {len(selected)} upload(s)."))

    def _needs_processing(self, upload, options):
        try:
            job = upload.ai_job
        except AIProcessingJob.DoesNotExist:
            return True

        if options["failed"] and job.status == AIProcessingJob.STATUS_FAILED:
            return True

        if options["retry_stuck"] and job.status == AIProcessingJob.STATUS_PROCESSING:
            return job.updated_at <= timezone.now() - STALE_PROCESSING_AFTER

        return job.status in {
            AIProcessingJob.STATUS_PENDING,
            AIProcessingJob.STATUS_FAILED,
        }
