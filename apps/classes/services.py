from django.db.models import Q, Count


class ClassService:
    """Business logic for classes"""
    
    @staticmethod
    def search_classes(query, user=None):
        """Search public classes or user's classes"""
        from .models import Class
        
        qs = Class.objects.filter(
            Q(name__icontains=query) | Q(class_code__icontains=query)
        )
        
        if user:
            qs = qs.filter(Q(is_public=True) | Q(members=user)).distinct()
        else:
            qs = qs.filter(is_public=True)
        
        return qs.annotate(total_members=Count('members')).order_by('-created_at')
    
    @staticmethod
    def user_can_access_class(user, class_obj):
        """Check if user can access class"""
        return class_obj.is_public or class_obj.members.filter(id=user.id).exists()

    @staticmethod
    def user_can_manage_class(user, class_obj):
        """Check whether a user can manage class-level settings or delegates."""
        if not user or not user.is_authenticated:
            return False
        if class_obj.creator_id == user.id:
            return True
        membership = class_obj.memberships.filter(user=user).only('role').first()
        return bool(membership and membership.role in {'lecturer', 'representative'})
