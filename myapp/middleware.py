from django.utils import timezone
from django.utils.deprecation import MiddlewareMixin


class UpdateLastSeenMiddleware(MiddlewareMixin):
    def process_view(self, request, view_func, view_args, view_kwargs):
        if request.user.is_authenticated:
            request.user.info.last_seen = timezone.now()
            request.user.info.save(update_fields=['last_seen'])
        return None


class AutoGeolocationMiddleware(MiddlewareMixin):
    """
    Middleware to auto-detect user location from IP address.
    Only runs once per user (when they don't have coordinates set).
    Uses a session flag to avoid repeated API calls.
    """
    
    def process_view(self, request, view_func, view_args, view_kwargs):
        if not request.user.is_authenticated:
            return None
        
        # Skip if already checked this session
        if request.session.get('geolocation_checked'):
            return None
        
        # Mark as checked for this session
        request.session['geolocation_checked'] = True
        
        user_info = request.user.info
        
        # Skip if user already has coordinates
        if user_info.latitude and user_info.longitude:
            return None
        
        # Try to get location from IP (async-friendly, non-blocking)
        try:
            from .utils.geolocation import update_user_location_from_ip
            update_user_location_from_ip(user_info, request)
        except Exception:
            # Don't break the request if geolocation fails
            pass
        
        return None