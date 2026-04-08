"""
Django management command to manually upload logs to MinIO
Usage: python manage.py upload_logs
"""
from django.core.management.base import BaseCommand
from django.conf import settings
from apps.core.utils.log_handler import MinIOLogSync
from pathlib import Path


class Command(BaseCommand):
    help = 'Upload log files to MinIO S3 storage'

    def add_arguments(self, parser):
        parser.add_argument(
            '--all',
            action='store_true',
            help='Upload all log files including backups',
        )

    def handle(self, *args, **options):
        log_dir = settings.LOG_DIR
        log_file = settings.LOG_FILE
        bucket_name = settings.AWS_STORAGE_BUCKET_NAME
        
        self.stdout.write(self.style.SUCCESS(f'Starting log upload to MinIO bucket: {bucket_name}'))
        
        # Upload current log file
        sync = MinIOLogSync(log_file, bucket_name, s3_prefix='logs')
        if sync.sync_current_log():
            self.stdout.write(self.style.SUCCESS(f'✓ Uploaded current log: {log_file.name}'))
        else:
            self.stdout.write(self.style.ERROR(f'✗ Failed to upload: {log_file.name}'))
        
        # Upload all backup log files if --all flag is used
        if options['all']:
            log_files = sorted(Path(log_dir).glob('*.log*'))
            for log_path in log_files:
                if log_path.name != log_file.name:
                    s3_key = f"logs/backups/{log_path.name}"
                    if sync.uploader.upload_log_file(log_path, s3_key):
                        self.stdout.write(self.style.SUCCESS(f'✓ Uploaded backup: {log_path.name}'))
                    else:
                        self.stdout.write(self.style.ERROR(f'✗ Failed to upload: {log_path.name}'))
        
        self.stdout.write(self.style.SUCCESS('Log upload completed'))
