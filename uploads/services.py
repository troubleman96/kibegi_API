from django.core.exceptions import ValidationError
import os


class FileHandler:
    """Handle file validation and processing"""
    MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB
    
    ALLOWED_EXTENSIONS = {
        'pdf', 'doc', 'docx', 'ppt', 'pptx', 'xls', 'xlsx',
        'txt', 'csv', 'zip', 'rar',
        'jpg', 'jpeg', 'png', 'gif',
        'mp4', 'mp3'
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
