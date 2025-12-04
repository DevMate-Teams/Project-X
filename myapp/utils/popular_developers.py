"""
Utility to fetch popular developers for empty feed state.
Ranks developers by total log count.
"""
from myapp.models import userinfo
from logs.models import Log
from django.db.models import Count


def get_popular_developers(current_user, limit=10):
    """
    Get popular developers ranked by log count.
    Excludes current user and users already followed.
    
    Args:
        current_user: User object of current user
        limit: Number of developers to return (default: 10)
    
    Returns:
        List of userinfo objects with annotated log_count
    """
    # Get IDs of users current user follows
    following_ids = current_user.info.get_following().values_list('id', flat=True)
    
    # Get popular developers
    popular_devs = userinfo.objects.annotate(
        log_count=Count('mind_logs')
    ).filter(
        log_count__gt=0  # Must have at least 1 log
    ).exclude(
        id=current_user.info.id  # Exclude self
    ).exclude(
        id__in=following_ids  # Exclude already followed
    ).select_related(
        'user', 'coding_style'
    ).order_by('-log_count')[:limit]
    
    return list(popular_devs)
