"""
Signal handlers for logs app - includes file cleanup and notification creation
"""
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
from django.core.files.storage import default_storage
from django.contrib.contenttypes.models import ContentType
import re

from .models import Log, Comment, Reaction, Notification
from myapp.models import follow


@receiver(post_delete, sender=Log)
def delete_log_snapshot(sender, instance, **kwargs):
    """Clean up snapshot file when log is deleted"""
    if instance.snap_shot and instance.snap_shot.name:
        if default_storage.exists(instance.snap_shot.name):
            default_storage.delete(instance.snap_shot.name)


# ============= NOTIFICATION SIGNALS =============

@receiver(post_save, sender=Comment)
def create_comment_notification(sender, instance, created, **kwargs):
    """
    Create notification when someone comments on a log or replies to a comment
    """
    if not created:
        return
    
    # Don't notify if user comments on their own log
    if instance.mindlog.user == instance.user:
        return
    
    # Determine notification type and recipient
    if instance.parent_comment:
        # This is a reply to a comment
        recipient = instance.parent_comment.user
        verb = 'replied to your comment on'
        notification_type = 'reply'
    else:
        # This is a comment on a log
        recipient = instance.mindlog.user
        verb = 'commented on your log'
        notification_type = 'comment'
    
    # Don't notify if replying to yourself
    if recipient == instance.user:
        return
    
    # Create the notification
    Notification.objects.create(
        recipient=recipient,
        actor=instance.user,
        verb=verb,
        target=instance.mindlog,
        action_object=instance,
        notification_type=notification_type
    )
    
    # Check for @mentions in the comment
    create_mention_notifications(instance.content, instance.user, instance.mindlog, instance, 'comment_mention')


@receiver(post_save, sender=Reaction)
def create_reaction_notification(sender, instance, created, **kwargs):
    """
    Create notification when someone reacts to a log
    """
    if not created:
        return
    
    # Don't notify if user reacts to their own log
    if instance.mindlog.user == instance.user:
        return
    
    Notification.objects.create(
        recipient=instance.mindlog.user,
        actor=instance.user,
        verb=f'reacted {instance.emoji} to your log',
        target=instance.mindlog,
        action_object=instance,
        notification_type='reaction'
    )


@receiver(post_save, sender=follow)
def create_follow_notification(sender, instance, created, **kwargs):
    """
    Create notification when someone follows a user
    """
    if not created:
        return
    
    Notification.objects.create(
        recipient=instance.following,
        actor=instance.follower,
        verb='started following you',
        target=instance.follower,  # Target is the follower's profile
        notification_type='follow'
    )


@receiver(post_save, sender=Log)
def create_log_mention_notifications(sender, instance, created, **kwargs):
    """
    Create notifications for @mentions in log content
    """
    if not created:
        return
    
    create_mention_notifications(instance.content, instance.user, instance, None, 'mention')


def create_mention_notifications(content, actor, log, action_object=None, notification_type='mention'):
    """
    Parse content for @mentions and create notifications
    
    Args:
        content: Text content to parse for mentions
        actor: User who created the content
        log: The log being mentioned in
        action_object: Optional action object (e.g., Comment)
        notification_type: Type of mention notification
    """
    from myapp.models import userinfo
    
    # Find all @mentions in the content
    mention_pattern = r'@(\w+)'
    mentioned_usernames = re.findall(mention_pattern, content)
    
    if not mentioned_usernames:
        return
    
    # Get unique usernames
    mentioned_usernames = set(mentioned_usernames)
    
    # Find users and create notifications
    for username in mentioned_usernames:
        try:
            mentioned_user = userinfo.objects.select_related('user').get(user__username=username)
            
            # Don't notify if mentioning yourself
            if mentioned_user == actor:
                continue
            
            # Don't notify the log owner if they're mentioned in their own log
            if mentioned_user == log.user and not action_object:
                continue
            
            # Create notification
            verb = 'mentioned you in a comment on' if notification_type == 'comment_mention' else 'mentioned you in a log'
            
            Notification.objects.create(
                recipient=mentioned_user,
                actor=actor,
                verb=verb,
                target=log,
                action_object=action_object,
                notification_type=notification_type
            )
        except userinfo.DoesNotExist:
            # Username doesn't exist, skip
            continue