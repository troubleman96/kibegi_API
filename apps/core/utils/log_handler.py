"""
Custom logging handler to upload log files to MinIO S3
"""
import boto3
import threading
import time
from logging.handlers import RotatingFileHandler
from datetime import datetime
from pathlib import Path
from decouple import config


class MinIOLogUploader:
    """Background thread that uploads rotated log files to MinIO"""
    
    def __init__(self, log_dir, bucket_name):
        self.log_dir = log_dir
        self.bucket_name = bucket_name
        self.s3_client = None
        self.running = False
        
    def get_s3_client(self):
        """Lazy initialization of S3 client"""
        if self.s3_client is None:
            try:
                self.s3_client = boto3.client(
                    's3',
                    endpoint_url=config('AWS_S3_ENDPOINT_URL', default='https://storage.kibegi.com'),
                    aws_access_key_id=config('AWS_ACCESS_KEY_ID', default=''),
                    aws_secret_access_key=config('AWS_SECRET_ACCESS_KEY', default=''),
                    region_name=config('AWS_S3_REGION_NAME', default='us-east-1'),
                )
            except Exception as e:
                print(f"Failed to initialize S3 client: {e}")
        return self.s3_client
        
    def upload_log_file(self, local_path, s3_key):
        """Upload a single log file to MinIO"""
        try:
            s3 = self.get_s3_client()
            if s3 is None:
                return False
                
            s3.upload_file(
                str(local_path),
                self.bucket_name,
                s3_key
            )
            print(f"Uploaded log file to MinIO: {s3_key}")
            return True
        except Exception as e:
            print(f"Failed to upload log to MinIO: {e}")
            return False


class MinIORotatingFileHandler(RotatingFileHandler):
    """
    RotatingFileHandler that uploads rotated log files to MinIO.
    Inherits from RotatingFileHandler and adds MinIO upload on rotation.
    """
    
    def __init__(self, filename, mode='a', maxBytes=0, backupCount=0,
                 encoding=None, delay=False, bucket_name='kibegi-uploads',
                 s3_prefix='logs'):
        Path(filename).parent.mkdir(parents=True, exist_ok=True)
        super().__init__(filename, mode, maxBytes, backupCount, encoding, delay)
        self.bucket_name = bucket_name
        self.s3_prefix = s3_prefix
        self.uploader = MinIOLogUploader(self.baseFilename, bucket_name)
        
    def doRollover(self):
        """
        Override doRollover to upload the rotated file to MinIO
        """
        # Perform the standard rotation
        super().doRollover()
        
        # Upload the rotated file in a background thread
        if self.backupCount > 0:
            # The most recent backup file
            rotated_file = f"{self.baseFilename}.1"
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            s3_key = f"{self.s3_prefix}/kibegi_api_{timestamp}.log"
            
            # Upload in background thread to not block logging
            thread = threading.Thread(
                target=self.uploader.upload_log_file,
                args=(rotated_file, s3_key),
                daemon=True
            )
            thread.start()


class MinIOLogSync:
    """
    Periodic uploader that syncs current log file to MinIO
    Run this as a scheduled task or periodic background job
    """
    
    def __init__(self, log_file, bucket_name='kibegi-uploads', s3_prefix='logs'):
        self.log_file = log_file
        self.bucket_name = bucket_name
        self.s3_prefix = s3_prefix
        self.uploader = MinIOLogUploader(log_file, bucket_name)
        
    def sync_current_log(self):
        """Upload current active log file"""
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            s3_key = f"{self.s3_prefix}/current/kibegi_api_current.log"
            return self.uploader.upload_log_file(self.log_file, s3_key)
        except Exception as e:
            print(f"Failed to sync current log: {e}")
            return False
