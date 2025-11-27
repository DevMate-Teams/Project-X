from django.utils import timezone
from datetime import timedelta
from django.db.models import Avg
from logs.models import Log
import math

def get_24h_log_stats():
    now = timezone.now()
    last_24h = now - timedelta(hours=24)

    logs_qs = Log.objects.filter(timestamp__gte=last_24h).order_by("-timestamp")
    
    stats = {
        "logs_qs": logs_qs,
        "logs_fired": logs_qs.count(),
        "logs_per_min": math.ceil(logs_qs.count() / (24 * 60)),
    }
    return stats

def streak_calculation(logs, user=None):
    """
    Calculate current streak (consecutive days with logs).
    Optimized with database-level date extraction and early termination.
    
    Args:
        logs: QuerySet of Log objects
        user: Django User object (for timezone conversion)
    
    Returns:
        int: Current streak count in days
    """
    # Use dates() for efficient unique date extraction at database level
    # Order DESC to start from most recent
    log_dates = list(logs.dates('timestamp', 'day', order='DESC'))
    
    if not log_dates:
        return 0
    
    # Get today in user's timezone if provided, else server timezone
    if user:
        from myapp.timezone_utils import user_today
        today = user_today(user)
    else:
        today = timezone.now().date()
    
    # If the most recent log is not today or yesterday, streak is broken
    most_recent = log_dates[0]
    if most_recent < today - timedelta(days=1):
        return 0
    
    streak = 0
    # Start from today or most recent log date
    current_check_date = today if most_recent == today else most_recent
    
    for log_date in log_dates:
        # Check if this log matches our expected date
        if log_date == current_check_date:
            streak += 1
            current_check_date -= timedelta(days=1)
        elif log_date < current_check_date:
            # There's a gap - streak is broken
            break
    
    return streak


def calculate_max_streak(logs):
    """
    Calculate maximum streak (longest consecutive-day logging streak).
    Optimized with database-level date extraction.
    
    Args:
        logs: QuerySet of Log objects
    
    Returns:
        int: Maximum streak count in days
    """
    # Use dates() for efficient unique date extraction at database level
    log_dates = list(logs.dates('timestamp', 'day', order='ASC'))
    
    if not log_dates:
        return 0
    
    max_streak = 1
    current_streak = 1
    
    for i in range(1, len(log_dates)):
        if log_dates[i] == log_dates[i-1] + timedelta(days=1):
            current_streak += 1
            max_streak = max(max_streak, current_streak)
        else:
            current_streak = 1
    
    return max_streak


