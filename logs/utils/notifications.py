"""
Utility functions for notification system
"""
from django.db.models import Q, Prefetch
from django.contrib.contenttypes.models import ContentType
from logs.models import Notification
from datetime import datetime, timedelta
from django.utils import timezone


def create_notification(recipient, actor, verb, target, action_object=None, notification_type=''):
    """
    Generic notification creator
    
    Args:
        recipient: userinfo object who receives the notification
        actor: userinfo object who triggered the notification
        verb: String describing the action
        target: The object being acted upon
        action_object: Optional object representing the action itself
        notification_type: Type from NOTIFICATION_TYPES choices
    
    Returns:
        Notification object
    """
    target_ct = ContentType.objects.get_for_model(target)
    
    action_ct = None
    action_id = None
    if action_object:
        action_ct = ContentType.objects.get_for_model(action_object)
        action_id = action_object.pk
    
    return Notification.objects.create(
        recipient=recipient,
        actor=actor,
        verb=verb,
        target_content_type=target_ct,
        target_object_id=target.pk,
        action_content_type=action_ct,
        action_object_id=action_id,
        notification_type=notification_type
    )


def get_user_notifications(user, unread_only=False, notification_type=None, limit=None, page_size=None, offset=0):
    """
    Fetch notifications for a user with optional filtering and pagination
    
    Args:
        user: User object or userinfo object
        unread_only: Boolean to filter only unread notifications
        notification_type: Optional type filter
        limit: Optional limit on number of notifications (deprecated, use page_size)
        page_size: Number of notifications per page (for pagination)
        offset: Starting position for pagination
    
    Returns:
        QuerySet of Notification objects
    """
    from myapp.models import userinfo
    
    # Get userinfo if User object is passed
    if hasattr(user, 'info'):
        user = user.info
    
    # Base query with optimizations
    notifications = Notification.objects.filter(
        recipient=user
    ).select_related(
        'actor__user',
        'recipient__user',
        'target_content_type',
        'action_content_type'
    ).order_by('-timestamp')
    
    # Apply filters
    if unread_only:
        notifications = notifications.filter(is_read=False)
    
    if notification_type:
        notifications = notifications.filter(notification_type=notification_type)
    
    # Apply pagination or limit
    if page_size:
        end = offset + page_size
        notifications = notifications[offset:end]
    elif limit:
        notifications = notifications[:limit]
    
    return notifications


def get_notification_count(user, unread_only=True):
    """
    Get count of notifications for badge display
    
    Args:
        user: User object or userinfo object
        unread_only: Boolean to count only unread notifications
    
    Returns:
        Integer count
    """
    from myapp.models import userinfo
    
    # Get userinfo if User object is passed
    if hasattr(user, 'info'):
        user = user.info
    
    query = Notification.objects.filter(recipient=user)
    
    if unread_only:
        query = query.filter(is_read=False)
    
    return query.count()


def mark_as_read(notification_ids):
    """
    Bulk mark notifications as read
    
    Args:
        notification_ids: List of notification IDs or single ID
    
    Returns:
        Number of notifications updated
    """
    if isinstance(notification_ids, (int, str)):
        notification_ids = [notification_ids]
    
    return Notification.objects.filter(
        id__in=notification_ids,
        is_read=False
    ).update(is_read=True)


def mark_all_as_read(user):
    """
    Mark all notifications as read for a user
    
    Args:
        user: User object or userinfo object
    
    Returns:
        Number of notifications updated
    """
    from myapp.models import userinfo
    
    # Get userinfo if User object is passed
    if hasattr(user, 'info'):
        user = user.info
    
    return Notification.objects.filter(
        recipient=user,
        is_read=False
    ).update(is_read=True)


def group_notifications_by_date(notifications):
    """
    Group notifications by time periods (Today, Yesterday, This Week, etc.)
    
    Args:
        notifications: QuerySet or list of Notification objects
    
    Returns:
        OrderedDict with time period keys and notification lists
    """
    from collections import OrderedDict
    
    now = timezone.now()
    today = now.date()
    yesterday = today - timedelta(days=1)
    week_ago = today - timedelta(days=7)
    
    grouped = OrderedDict([
        ('Today', []),
        ('Yesterday', []),
        ('This Week', []),
        ('Earlier', [])
    ])
    
    for notification in notifications:
        notif_date = notification.timestamp.date()
        
        if notif_date == today:
            grouped['Today'].append(notification)
        elif notif_date == yesterday:
            grouped['Yesterday'].append(notification)
        elif notif_date > week_ago:
            grouped['This Week'].append(notification)
        else:
            grouped['Earlier'].append(notification)
    
    # Remove empty groups
    return OrderedDict((k, v) for k, v in grouped.items() if v)


def delete_old_notifications(days=30):
    """
    Delete read notifications older than specified days
    Useful for cleanup tasks
    
    Args:
        days: Number of days to keep notifications
    
    Returns:
        Number of notifications deleted
    """
    cutoff_date = timezone.now() - timedelta(days=days)
    
    count, _ = Notification.objects.filter(
        is_read=True,
        timestamp__lt=cutoff_date
    ).delete()
    
    return count
