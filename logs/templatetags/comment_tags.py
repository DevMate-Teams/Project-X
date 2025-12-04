import re
from django import template
from django.utils.safestring import mark_safe
from django.utils.html import escape
from django.urls import reverse

register = template.Library()

@register.filter(name='parse_mentions')
def parse_mentions(text):
    """
    Parse @mentions in text and convert them to clickable user profile links.
    
    Usage in template:
        {{ comment.content|parse_mentions }}
    
    Example:
        Input: "Hey @john_doe, check this out!"
        Output: "Hey <a href='/user-profile/john_doe/'>@john_doe</a>, check this out!"
    """
    if not text:
        return text
    
    # Escape HTML first to prevent XSS attacks
    escaped_text = escape(text)
    
    # Match @username patterns (alphanumeric, underscores, and dots)
    # Username should start with alphanumeric and can contain underscores/dots
    pattern = r'@([a-zA-Z0-9_.]+)'
    
    def replace_mention(match):
        username = match.group(1)
        # Use Django's reverse() would be ideal but we need the username in the URL
        # So we'll construct it directly following the URL pattern
        profile_url = f'/user-profile/{username}/'
        return f'<a href="{profile_url}" class="text-green-500 hover:text-green-600 transition-colors font-semibold">@{username}</a>'
    
    result = re.sub(pattern, replace_mention, escaped_text)
    
    return mark_safe(result)
