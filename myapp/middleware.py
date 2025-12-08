from django.utils import timezone
from django.utils.deprecation import MiddlewareMixin


class UpdateLastSeenMiddleware(MiddlewareMixin):
    def process_view(self, request, view_func, view_args, view_kwargs):
        if request.user.is_authenticated:
            request.user.info.last_seen = timezone.now()
            request.user.info.save(update_fields=['last_seen'])
        return None