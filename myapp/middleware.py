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
    Runs periodically to refresh stale IP-based location data.
    Uses a session flag to avoid repeated API calls within the same session.
    
    IP location is refreshed every 24 hours to handle users who move.
    This is separate from browser geolocation (which has its own 7-day refresh).
    """
    
    def process_view(self, request, view_func, view_args, view_kwargs):
        if not request.user.is_authenticated:
            return None
        
        # Skip if already checked this session
        if request.session.get('ip_geolocation_checked'):
            return None
        
        # Mark as checked for this session
        request.session['ip_geolocation_checked'] = True
        
        user_info = request.user.info
        
        # Try to update location from IP (handles staleness check internally)
        try:
            from .utils.geolocation import update_user_location_from_ip, is_ip_location_stale
            
            # Only make API call if IP location is stale or not set
            if is_ip_location_stale(user_info):
                update_user_location_from_ip(user_info, request)
        except Exception:
            # Don't break the request if geolocation fails
            pass
        
        return None