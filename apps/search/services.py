import logging
from typing import Any, Dict, List, Optional

from django.contrib.auth import get_user_model
from django.db.models import Count, Q

logger = logging.getLogger('kibegi')
User = get_user_model()

ALL_CATEGORIES = ['users', 'classes', 'files', 'friends', 'library']


class SearchService:
    MIN_QUERY_LENGTH = 2
    DEFAULT_LIMIT = 10

    @classmethod
    def search(
        cls,
        query: str,
        user,
        limit: int = DEFAULT_LIMIT,
        categories: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        logger.info(f"Search by {user.email}: query='{query}'")

        query = query.strip()
        search_categories = categories if categories else ALL_CATEGORIES

        results: Dict[str, List] = {}
        counts: Dict[str, int] = {}
        total = 0

        handlers = {
            'users': lambda: cls._search_users(query, user, limit),
            'classes': lambda: cls._search_classes(query, user, limit),
            'files': lambda: cls._search_files(query, user, limit),
            'friends': lambda: cls._search_friends(query, user, limit),
            'library': lambda: cls._search_library(query, limit),
        }

        for category in search_categories:
            handler = handlers.get(category)
            if handler is None:
                continue
            cat_results = handler()
            results[category] = cat_results
            counts[category] = len(cat_results)
            total += len(cat_results)

        cls._save_history(user, query, total, search_categories)

        logger.info(f"Search done: query='{query}', total={total}")
        return {
            'query': query,
            'total_results': total,
            'results': results,
            'counts': counts,
        }

    @classmethod
    def suggestions(cls, query: str, user, limit: int = 5) -> List[Dict]:
        """Fast autocomplete — prefix matches only, no history saved."""
        query = query.strip()
        results: List[Dict] = []

        users = User.objects.filter(
            Q(full_name__istartswith=query) | Q(email__istartswith=query),
            is_active=True,
        ).exclude(id=user.id)[:limit]
        for u in users:
            results.append({'type': 'user', 'label': u.full_name, 'sub': u.email})

        if len(results) < limit:
            from apps.classes.models import Class
            classes = Class.objects.filter(
                name__istartswith=query,
            ).filter(
                Q(members=user) | Q(is_public=True)
            ).distinct()[: limit - len(results)]
            for c in classes:
                results.append({'type': 'class', 'label': c.name, 'sub': c.class_code})

        if len(results) < limit:
            from apps.library.models import LibraryItem
            items = LibraryItem.objects.filter(
                title__istartswith=query,
                status='public',
            )[: limit - len(results)]
            for item in items:
                results.append({'type': 'library', 'label': item.title, 'sub': item.file_type})

        return results

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _save_history(user, query: str, result_count: int, categories) -> None:
        try:
            from apps.search.models import SearchHistory
            SearchHistory.objects.create(
                user=user,
                query=query,
                result_count=result_count,
                categories_searched=list(categories),
            )
        except Exception as exc:
            logger.warning(f"Failed to save search history: {exc}")

    @staticmethod
    def _search_users(query: str, current_user, limit: int) -> List[Dict]:
        users = User.objects.filter(
            Q(email__icontains=query) | Q(full_name__icontains=query),
            is_active=True,
        ).exclude(id=current_user.id).order_by('full_name')[:limit]

        return [
            {
                'id': str(u.id),
                'type': 'user',
                'email': u.email,
                'full_name': u.full_name,
                'user_type': u.user_type,
                'profile_image': u.profile_image.name if u.profile_image else None,
                'profile_image_url': u.profile_image.url if u.profile_image else None,
            }
            for u in users
        ]

    @staticmethod
    def _search_classes(query: str, current_user, limit: int) -> List[Dict]:
        from apps.classes.models import Class

        classes = (
            Class.objects.filter(
                Q(name__icontains=query)
                | Q(description__icontains=query)
                | Q(class_code__icontains=query)
            )
            .filter(Q(members=current_user) | Q(is_public=True))
            .annotate(member_count=Count('members'))
            .distinct()
            .order_by('-created_at')[:limit]
        )

        return [
            {
                'id': str(c.id),
                'type': 'class',
                'name': c.name,
                'description': c.description[:100] + '...' if len(c.description) > 100 else c.description,
                'class_code': c.class_code,
                'is_verified': c.is_verified,
                'member_count': c.member_count,
                'creator_name': c.creator.full_name,
            }
            for c in classes
        ]

    @staticmethod
    def _search_files(query: str, current_user, limit: int) -> List[Dict]:
        from apps.sharing.models import SharedFile
        from apps.uploads.models import Upload

        shared_ids = SharedFile.objects.filter(
            shared_with=current_user, status='accepted'
        ).values_list('upload_id', flat=True)

        files = (
            Upload.objects.filter(
                Q(file_name__icontains=query),
                Q(uploader=current_user) | Q(id__in=shared_ids),
                is_deleted=False,
            )
            .select_related('uploader', 'class_obj')
            .order_by('-created_at')[:limit]
        )

        return [
            {
                'id': str(f.id),
                'type': 'file',
                'file_name': f.file_name,
                'file_type': f.file_type,
                'file_size': f.file_size,
                'file_code': f.file_code,
                'uploader_name': f.uploader.full_name,
                'class_name': f.class_obj.name if f.class_obj else None,
                'is_own': f.uploader == current_user,
                'created_at': f.created_at.isoformat(),
            }
            for f in files
        ]

    @staticmethod
    def _search_friends(query: str, current_user, limit: int) -> List[Dict]:
        from apps.friends.models import Friendship

        friendships = (
            Friendship.objects.filter(
                Q(user=current_user) | Q(friend=current_user),
                status='accepted',
            )
            .filter(
                Q(user__email__icontains=query)
                | Q(user__full_name__icontains=query)
                | Q(friend__email__icontains=query)
                | Q(friend__full_name__icontains=query)
            )
            .select_related('user', 'friend')[: limit * 2]
        )

        results: List[Dict] = []
        seen: set = set()

        for fs in friendships:
            other = fs.friend if fs.user == current_user else fs.user
            if not (
                query.lower() in other.email.lower()
                or query.lower() in other.full_name.lower()
            ):
                continue
            if other.id in seen:
                continue
            seen.add(other.id)
            results.append(
                {
                    'id': str(fs.id),
                    'type': 'friend',
                    'friend_id': str(other.id),
                    'friend_email': other.email,
                    'friend_name': other.full_name,
                    'friend_type': other.user_type,
                    'friend_profile_image': other.profile_image.name if other.profile_image else None,
                    'friend_profile_image_url': other.profile_image.url if other.profile_image else None,
                    'nickname': fs.nickname if fs.user == current_user else '',
                    'accepted_at': fs.accepted_at.isoformat() if fs.accepted_at else None,
                }
            )
            if len(results) >= limit:
                break

        return results

    @staticmethod
    def _search_library(query: str, limit: int) -> List[Dict]:
        from apps.library.models import LibraryItem

        items = (
            LibraryItem.objects.filter(
                Q(title__icontains=query)
                | Q(description__icontains=query)
                | Q(subject__icontains=query)
                | Q(author_name__icontains=query)
                | Q(course_code__icontains=query),
                status='public',
            )
            .select_related('category', 'uploaded_by')
            .order_by('-is_featured', '-view_count')[:limit]
        )

        return [
            {
                'id': str(item.id),
                'type': 'library',
                'item_code': item.item_code,
                'title': item.title,
                'description': item.description[:120] + '...' if len(item.description) > 120 else item.description,
                'file_type': item.file_type,
                'subject': item.subject,
                'course_code': item.course_code,
                'author_name': item.author_name,
                'category_name': item.category.name if item.category else None,
                'is_featured': item.is_featured,
                'view_count': item.view_count,
                'download_count': item.download_count,
            }
            for item in items
        ]
