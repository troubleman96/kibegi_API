"""
Core services for the Kibegi API.

This module contains cross-cutting services that operate across multiple apps,
including the global search functionality.
"""

import logging
from typing import Dict, List, Any, Optional
from django.db.models import Q, Count
from django.contrib.auth import get_user_model

logger = logging.getLogger('kibegi')
User = get_user_model()


class GlobalSearchService:
    """
    Service for searching across all Kibegi apps.
    
    Searches through:
    - Users (by name, email)
    - Classes (by name, description, code)
    - Uploads/Files (by filename)
    - Friends (by friend's name, email)
    
    Features:
    - Minimum query length validation
    - Result limiting per category
    - Permission-aware results (users only see what they have access to)
    - Relevance-based ordering
    """
    
    # Minimum characters required for search
    MIN_QUERY_LENGTH = 2
    
    # Default limit per category
    DEFAULT_LIMIT = 10
    
    @classmethod
    def search(
        cls,
        query: str,
        user,
        limit: int = DEFAULT_LIMIT,
        categories: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Perform a global search across all apps.
        
        Args:
            query: Search query string (min 2 characters)
            user: The authenticated user performing the search
            limit: Maximum results per category (default: 10)
            categories: Optional list of categories to search.
                       If None, searches all categories.
                       Options: ['users', 'classes', 'files', 'friends']
        
        Returns:
            Dict with categorized search results and metadata
        
        Example:
            {
                "query": "john",
                "total_results": 15,
                "results": {
                    "users": [...],
                    "classes": [...],
                    "files": [...],
                    "friends": [...]
                },
                "counts": {
                    "users": 5,
                    "classes": 3,
                    "files": 4,
                    "friends": 3
                }
            }
        """
        logger.info(f"Global search initiated by {user.email}: query='{query}'")
        
        # Validate query
        if not query or len(query.strip()) < cls.MIN_QUERY_LENGTH:
            logger.warning(f"Search query too short: '{query}'")
            return {
                "query": query,
                "total_results": 0,
                "results": {},
                "counts": {},
                "error": f"Search query must be at least {cls.MIN_QUERY_LENGTH} characters"
            }
        
        query = query.strip()
        
        # Determine which categories to search
        all_categories = ['users', 'classes', 'files', 'friends']
        search_categories = categories if categories else all_categories
        
        results = {}
        counts = {}
        total = 0
        
        # Search each category
        for category in search_categories:
            if category == 'users':
                category_results = cls._search_users(query, user, limit)
            elif category == 'classes':
                category_results = cls._search_classes(query, user, limit)
            elif category == 'files':
                category_results = cls._search_files(query, user, limit)
            elif category == 'friends':
                category_results = cls._search_friends(query, user, limit)
            else:
                continue
            
            results[category] = category_results
            counts[category] = len(category_results)
            total += len(category_results)
        
        logger.info(f"Global search completed: query='{query}', total_results={total}")
        
        return {
            "query": query,
            "total_results": total,
            "results": results,
            "counts": counts
        }
    
    @staticmethod
    def _search_users(query: str, current_user, limit: int) -> List[Dict]:
        """
        Search for users by email or full name.
        
        Returns active users excluding the current user.
        """
        logger.debug(f"Searching users for: '{query}'")
        
        users = User.objects.filter(
            Q(email__icontains=query) | Q(full_name__icontains=query),
            is_active=True
        ).exclude(
            id=current_user.id
        ).order_by('full_name')[:limit]
        
        return [
            {
                "id": str(user.id),
                "type": "user",
                "email": user.email,
                "full_name": user.full_name,
                "user_type": user.user_type,
                "profile_image": user.profile_image.name if user.profile_image else None,
                "profile_image_url": user.profile_image.url if user.profile_image else None,
            }
            for user in users
        ]
    
    @staticmethod
    def _search_classes(query: str, current_user, limit: int) -> List[Dict]:
        """
        Search for classes by name, description, or class code.
        
        Returns classes the user is a member of or public classes.
        """
        logger.debug(f"Searching classes for: '{query}'")
        
        from apps.classes.models import Class
        
        # Search in classes user is member of OR public classes
        classes = Class.objects.filter(
            Q(name__icontains=query) | 
            Q(description__icontains=query) |
            Q(class_code__icontains=query)
        ).filter(
            Q(members=current_user) | Q(is_public=True)
        ).annotate(
            member_count=Count('members')
        ).distinct().order_by('-created_at')[:limit]
        
        return [
            {
                "id": str(cls.id),
                "type": "class",
                "name": cls.name,
                "description": cls.description[:100] + "..." if len(cls.description) > 100 else cls.description,
                "class_code": cls.class_code,
                "is_verified": cls.is_verified,
                "member_count": cls.member_count,
                "creator_name": cls.creator.full_name,
            }
            for cls in classes
        ]
    
    @staticmethod
    def _search_files(query: str, current_user, limit: int) -> List[Dict]:
        """
        Search for files/uploads by filename.
        
        Returns files uploaded by the user OR shared with the user (accepted).
        """
        logger.debug(f"Searching files for: '{query}'")
        
        from apps.uploads.models import Upload
        from apps.sharing.models import SharedFile
        
        # Get IDs of files shared with user (accepted)
        shared_file_ids = SharedFile.objects.filter(
            shared_with=current_user,
            status='accepted'
        ).values_list('upload_id', flat=True)
        
        # Search own uploads OR accepted shared files
        files = Upload.objects.filter(
            Q(file_name__icontains=query),
            Q(uploader=current_user) | Q(id__in=shared_file_ids),
            is_deleted=False
        ).select_related('uploader', 'class_obj').order_by('-created_at')[:limit]
        
        return [
            {
                "id": str(f.id),
                "type": "file",
                "file_name": f.file_name,
                "file_type": f.file_type,
                "file_size": f.file_size,
                "file_code": f.file_code,
                "uploader_name": f.uploader.full_name,
                "class_name": f.class_obj.name if f.class_obj else None,
                "is_own": f.uploader == current_user,
                "created_at": f.created_at.isoformat(),
            }
            for f in files
        ]
    
    @staticmethod
    def _search_friends(query: str, current_user, limit: int) -> List[Dict]:
        """
        Search for friends by name or email.
        
        Returns accepted friendships where the friend matches the query.
        """
        logger.debug(f"Searching friends for: '{query}'")
        
        from apps.friends.models import Friendship
        
        # Search in accepted friendships where user is either user or friend
        friendships = Friendship.objects.filter(
            Q(user=current_user) | Q(friend=current_user),
            status='accepted'
        ).filter(
            # Match the OTHER person in the friendship
            Q(user__email__icontains=query) | Q(user__full_name__icontains=query) |
            Q(friend__email__icontains=query) | Q(friend__full_name__icontains=query)
        ).select_related('user', 'friend')[:limit * 2]  # Get more to filter
        
        results = []
        seen_ids = set()
        
        for friendship in friendships:
            # Determine which user is the friend (not the current user)
            if friendship.user == current_user:
                friend = friendship.friend
            else:
                friend = friendship.user
            
            # Skip if doesn't match query (the current user matched instead)
            if not (query.lower() in friend.email.lower() or 
                    query.lower() in friend.full_name.lower()):
                continue
            
            # Avoid duplicates
            if friend.id in seen_ids:
                continue
            seen_ids.add(friend.id)
            
            results.append({
                "id": str(friendship.id),
                "type": "friend",
                "friend_id": str(friend.id),
                "friend_email": friend.email,
                "friend_name": friend.full_name,
                "friend_type": friend.user_type,
                "friend_profile_image": friend.profile_image.name if friend.profile_image else None,
                "friend_profile_image_url": friend.profile_image.url if friend.profile_image else None,
                "nickname": friendship.nickname if friendship.user == current_user else "",
                "accepted_at": friendship.accepted_at.isoformat() if friendship.accepted_at else None,
            })
            
            if len(results) >= limit:
                break
        
        return results
