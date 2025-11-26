from django.db import models
from myapp.models import userinfo
from django.utils.crypto import get_random_string
from django.db.models import F, Count

BASE62_ALPHABET = '0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'

def generate_base62_id(length=8):
    return get_random_string(length=length, allowed_chars=BASE62_ALPHABET)

def generate_unique_signature():
    while True:
        sig = f"sig-{generate_base62_id()}"
        if not Log.objects.filter(sig=sig).exists():
            return sig

class Log(models.Model):
    user = models.ForeignKey(userinfo, on_delete=models.CASCADE, related_name='mind_logs')
    content = models.TextField(max_length=255)
    snap_shot = models.ImageField(upload_to='log_snap_shot', blank=True, null=True)
    code_snippet = models.TextField(max_length=5000, blank=True, null=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    link = models.URLField(blank=True, null=True)

    # Unique signature
    sig = models.CharField(max_length=20, unique=True, default=generate_unique_signature)
    
    def total_comments(self):
        return self.comments.count()
    
    def total_reactions(self):
        return self.reactions.count()
    
    def get_reaction_counts(self):
        """Get count of each reaction type"""
        counts = self.reactions.values('emoji').annotate(count=Count('emoji'))
        return {item['emoji']: item['count'] for item in counts}
    
    def get_user_reaction(self, user):
        """Get the reaction by a specific user for this log"""
        try:
            return self.reactions.get(user=user.info if hasattr(user, 'info') else user)
        except:
            return None
    
    def has_user_reacted(self, user):
        """Check if user has reacted to this log"""
        return self.reactions.filter(user=user.info if hasattr(user, 'info') else user).exists()
    

    def __str__(self):
        return f"{self.user.user.username} ▸ {self.sig}"


class Comment(models.Model):
    """
    Comment model for Log entries
    """
    mindlog = models.ForeignKey(Log, on_delete=models.CASCADE, related_name='comments')
    user = models.ForeignKey(userinfo, on_delete=models.CASCADE, related_name='mindlog_comments')
    content = models.TextField(max_length=500)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    
    # Reply functionality (nested comments)
    parent_comment = models.ForeignKey('self', null=True, blank=True, on_delete=models.CASCADE, related_name='replies')
    
    # Reactions for comments
    likes = models.ManyToManyField(userinfo, related_name="liked_logs_comments", blank=True)
    
    class Meta:
        ordering = ['timestamp']
        indexes = [
            models.Index(fields=['mindlog', 'timestamp']),
            models.Index(fields=['user', 'timestamp']),
        ]
    
    def total_likes(self):
        return self.likes.count()
    
    def is_reply(self):
        return self.parent_comment is not None
    
    def get_replies(self):
        return self.replies.all().order_by('timestamp')
    
    def __str__(self):
        if self.is_reply():
            return f"{self.user.user.username} replied to {self.parent_comment.user.user.username} on {self.mindlog.sig}"
        return f"{self.user.user.username} commented on {self.mindlog.sig}"


class Reaction(models.Model):
    """
    Reaction model for MindLog entries with emoji reactions
    """
    REACTION_CHOICES = [
        ('❤️', 'Like'),
        ('🚀', 'Rocket'),
        ('💡', 'Insight'),
        ('😢', 'Sad'),
    ]
    
    mindlog = models.ForeignKey(Log, on_delete=models.CASCADE, related_name='reactions')
    user = models.ForeignKey(userinfo, on_delete=models.CASCADE, related_name='mindlog_reactions')
    emoji = models.CharField(max_length=10, choices=REACTION_CHOICES)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    
    class Meta:
        # Ensure one reaction per user per mindlog
        unique_together = ['mindlog', 'user']
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['mindlog', 'emoji']),
            models.Index(fields=['user', 'timestamp']),
        ]
    
    def __str__(self):
        return f"{self.user.user.username} reacted {self.emoji} to {self.mindlog.sig}"
    

