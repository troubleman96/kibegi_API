"""Business logic for sharing app"""

from django.db.models import Q
from .models import SharedFile


class SharingService:
    """
    Business logic service for file sharing operations.
    
    Handles:
    - Share permission validation
    - Querying shared files
    - Share request management
    """
    
    @staticmethod
    def can_share_file(user, upload):
        """
        Check if user has permission to share a file.
        
        Rules:
        - User must be the uploader (file owner)
        - File must not be deleted
        - User must be member of the file's class
        
        Args:
            user: User attempting to share
            upload: Upload object to share
            
        Returns:
            bool: True if user can share, False otherwise
        """
        # User must be the file uploader
        if upload.uploader != user:
            return False
        
        # File must not be deleted
        if upload.is_deleted:
            return False
        
        return True
    
    @staticmethod
    def can_receive_share(shared_with_user, upload):
        """
        Check if user can receive a file share.
        
        Rules:
        - User must be member of the file's class
        - User cannot be the file owner (can't share with yourself)
        
        Args:
            shared_with_user: User receiving the share
            upload: Upload object being shared
            
        Returns:
            bool: True if user can receive, False otherwise
        """
        # Cannot share with yourself
        if upload.uploader == shared_with_user:
            return False
        
        # Both users must be members of the file's class
        class_obj = upload.class_obj
        is_member = class_obj.members.filter(id=shared_with_user.id).exists()
        
        return is_member
    
    @staticmethod
    def get_shared_with_me(user, status=None):
        """
        Get files shared with the user.
        
        Args:
            user: User to get received shares for
            status: Optional filter by status ('pending', 'accepted', 'rejected')
                   If None, returns all statuses
        
        Returns:
            QuerySet of SharedFile objects
        """
        queryset = SharedFile.objects.filter(
            shared_with=user,
            upload__is_deleted=False  # Exclude deleted files
        ).select_related(
            'upload',           # Optimize: load upload data
            'shared_by',        # Optimize: load sharer data
            'upload__uploader', # Optimize: load original uploader
            'upload__class_obj' # Optimize: load class data
        )
        
        # Filter by status if specified
        if status:
            queryset = queryset.filter(status=status)
        
        return queryset
    
    @staticmethod
    def get_my_shares(user, status=None):
        """
        Get files shared by the user.
        
        Args:
            user: User to get shared files for
            status: Optional filter by status
            
        Returns:
            QuerySet of SharedFile objects
        """
        queryset = SharedFile.objects.filter(
            shared_by=user,
            upload__is_deleted=False
        ).select_related(
            'upload',
            'shared_with',
            'upload__class_obj'
        )
        
        if status:
            queryset = queryset.filter(status=status)
        
        return queryset
    
    @staticmethod
    def get_pending_requests(user):
        """
        Get pending share requests for user.
        
        Args:
            user: User to get pending requests for
            
        Returns:
            QuerySet of pending SharedFile objects
        """
        return SharingService.get_shared_with_me(user, status='pending')
    
    @staticmethod
    def get_accepted_shares(user):
        """
        Get accepted shares for user (files user can access).
        
        Args:
            user: User to get accepted shares for
            
        Returns:
            QuerySet of accepted SharedFile objects
        """
        return SharingService.get_shared_with_me(user, status='accepted')
    
    @staticmethod
    def share_exists(upload, shared_with_user):
        """
        Check if share already exists between upload and user.
        
        Args:
            upload: Upload object
            shared_with_user: User to check share with
            
        Returns:
            bool: True if share exists, False otherwise
        """
        return SharedFile.objects.filter(
            upload=upload,
            shared_with=shared_with_user
        ).exists()
    
    @staticmethod
    def get_share_by_id(share_id, user):
        """
        Get a specific share by ID, ensuring user has access.
        
        Args:
            share_id: UUID of the share
            user: User requesting access
            
        Returns:
            SharedFile object or None
        """
        try:
            # User must be either the sharer or recipient
            return SharedFile.objects.filter(
                Q(shared_by=user) | Q(shared_with=user),
                id=share_id
            ).first()
        except SharedFile.DoesNotExist:
            return None
    
    @staticmethod
    def create_share(upload, shared_by, shared_with, message=""):
        """
        Create a new file share.
        
        Args:
            upload: Upload object to share
            shared_by: User sharing the file
            shared_with: User receiving the share
            message: Optional message from sharer
            
        Returns:
            SharedFile object
            
        Raises:
            ValueError: If share already exists or validation fails
        """
        # Validate permissions
        if not SharingService.can_share_file(shared_by, upload):
            raise ValueError("You don't have permission to share this file")
        
        if not SharingService.can_receive_share(shared_with, upload):
            raise ValueError("Cannot share file with this user")
        
        # Check for existing share
        if SharingService.share_exists(upload, shared_with):
            raise ValueError("File already shared with this user")
        
        # Create share
        share = SharedFile.objects.create(
            upload=upload,
            shared_by=shared_by,
            shared_with=shared_with,
            message=message,
            status='pending'
        )

        try:
            from apps.notifications.services import NotificationService

            file_name = getattr(upload, "file_name", "a file")
            sharer_name = getattr(shared_by, "full_name", "Someone")
            content = f"{sharer_name} shared \"{file_name}\" with you"
            NotificationService.create_notification(
                user=shared_with,
                notification_type="share_request",
                content=content,
                related_id=str(share.id),
            )
        except Exception:
            # Sharing must succeed even if notifications fail.
            pass
        
        return share
    
    @staticmethod
    def bulk_share(upload, shared_by, user_ids, message=""):
        """
        Share file with multiple users at once.
        
        Args:
            upload: Upload object to share
            shared_by: User sharing the file
            user_ids: List of user IDs to share with
            message: Optional message
            
        Returns:
            dict with 'success' and 'errors' lists
        """
        from apps.authentication.models import User
        
        results = {
            'success': [],
            'errors': []
        }
        
        for user_id in user_ids:
            try:
                user = User.objects.get(id=user_id)
                share = SharingService.create_share(upload, shared_by, user, message)
                results['success'].append({
                    'user_id': user_id,
                    'share_id': str(share.id),
                    'user_name': user.full_name
                })
            except User.DoesNotExist:
                results['errors'].append({
                    'user_id': user_id,
                    'error': 'User not found'
                })
            except ValueError as e:
                results['errors'].append({
                    'user_id': user_id,
                    'error': str(e)
                })
        
        return results
