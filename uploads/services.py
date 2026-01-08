from django.core.exceptions import ValidationError
import os
import mimetypes


class FileHandler:
    """Handle file validation and processing"""
    MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
    
    ALLOWED_EXTENSIONS = {
        # Documents
        'pdf', 'doc', 'docx', 'txt', 'rtf', 'odt',
        # Spreadsheets
        'xls', 'xlsx', 'csv', 'ods',
        # Presentations
        'ppt', 'pptx', 'odp', 'key',
        # Images
        'jpg', 'jpeg', 'png', 'gif', 'bmp', 'svg', 'webp', 'ico',
        # Videos
        'mp4', 'avi', 'mov', 'wmv', 'flv', 'mkv', 'webm', 'm4v',
        # Audio
        'mp3', 'wav', 'ogg', 'flac', 'm4a', 'aac', 'wma',
        # Archives
        'zip', 'rar', 'tar', 'gz', '7z', 'bz2', 'xz'
    }
    
    @classmethod
    def validate_file(cls, file):
        """
        Validate file size and type.
        
        Args:
            file: The uploaded file object
            
        Returns:
            bool: True if valid
            
        Raises:
            ValidationError: If file is invalid
        """
        if file.size > cls.MAX_FILE_SIZE:
            raise ValidationError(f"File too large (max {cls.MAX_FILE_SIZE // (1024*1024)}MB)")
        
        ext = os.path.splitext(file.name)[1][1:].lower()
        if ext not in cls.ALLOWED_EXTENSIONS:
            raise ValidationError(f"File type '.{ext}' not allowed")
        
        return True
    
    @classmethod
    def detect_file_type(cls, filename):
        """
        Detect file type based on extension and MIME type.
        
        Args:
            filename: The name of the file
            
        Returns:
            str: File type category (document, image, video, etc.)
        """
        ext = os.path.splitext(filename)[1][1:].lower()
        mime_type, _ = mimetypes.guess_type(filename)
        
        # Map extensions and MIME types to categories
        if ext in ['pdf', 'doc', 'docx', 'txt', 'rtf', 'odt'] or (mime_type and 'text' in mime_type and ext not in ['csv']):
            return 'document'
        elif ext in ['xls', 'xlsx', 'csv', 'ods'] or (mime_type and 'spreadsheet' in mime_type):
            return 'spreadsheet'
        elif ext in ['ppt', 'pptx', 'odp', 'key'] or (mime_type and 'presentation' in mime_type):
            return 'presentation'
        elif ext in ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'svg', 'webp', 'ico'] or (mime_type and 'image' in mime_type):
            return 'image'
        elif ext in ['mp4', 'avi', 'mov', 'wmv', 'flv', 'mkv', 'webm', 'm4v'] or (mime_type and 'video' in mime_type):
            return 'video'
        elif ext in ['mp3', 'wav', 'ogg', 'flac', 'm4a', 'aac', 'wma'] or (mime_type and 'audio' in mime_type):
            return 'audio'
        elif ext in ['zip', 'rar', 'tar', 'gz', '7z', 'bz2', 'xz']:
            return 'archive'
        else:
            return 'other'
