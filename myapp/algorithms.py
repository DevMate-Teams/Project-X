from django.core.paginator import Paginator, EmptyPage
from itertools import chain
from .models import follow, skill, userinfo
from django.db.models import Q, Count, Exists, OuterRef, Subquery, Value, FloatField
from django.db.models.functions import Coalesce
from django.utils.timezone import now
from datetime import timedelta
from decimal import Decimal
import random
import math


def get_explore_users(filter_dev, request, count=200, order_by='-created_at'):
    # Step 1: Get followed user IDs and current user ID
    followed_ids = follow.objects.filter(
        follower=request.user.info
    ).values_list('following_id', flat=True)

    exclude_ids = list(followed_ids) + [request.user.info.id]

    # Step 2: Use `.only()` to limit fields fetched from DB for performance
    users = filter_dev.exclude(id__in=exclude_ids).only('id', 'profile_image', 'user__username').order_by(order_by)[:count]
    return users


# =============================================================================
# LOCAL FEED - MVP CONFIGURATION
# =============================================================================
# Simple distance-based filtering with timestamp sorting
LOCAL_RADIUS_KM = 250  # Show logs from users within 250 km


def haversine_distance(lat1, lon1, lat2, lon2):
    """
    Calculate the great-circle distance between two points on Earth
    using the Haversine formula.
    
    Args:
        lat1, lon1: Latitude and longitude of point 1 (in degrees)
        lat2, lon2: Latitude and longitude of point 2 (in degrees)
    
    Returns:
        Distance in kilometers
    """
    # Convert to floats if Decimal
    lat1 = float(lat1) if isinstance(lat1, Decimal) else lat1
    lon1 = float(lon1) if isinstance(lon1, Decimal) else lon1
    lat2 = float(lat2) if isinstance(lat2, Decimal) else lat2
    lon2 = float(lon2) if isinstance(lon2, Decimal) else lon2
    
    # Earth's radius in kilometers
    R = 6371.0
    
    # Convert degrees to radians
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)
    
    # Haversine formula
    a = math.sin(delta_lat / 2) ** 2 + \
        math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    
    return R * c


def _get_local_recommendation_reason(log, distance_km, shared_skills_count=0):
    """
    Generate recommendation reason for Local feed logs.
    Shows distance-based or skill-based labels.
    """
    if distance_km is None:
        return {
            'text': 'Nearby developer',
            'subtext': 'In your region',
            'icon': 'fa-map-marker'
        }
    
    if distance_km <= 5:
        return {
            'text': 'Very close',
            'subtext': f'{distance_km:.1f} km away',
            'icon': 'fa-map-marker'
        }
    elif distance_km <= 20:
        return {
            'text': 'Near you',
            'subtext': f'{distance_km:.1f} km away',
            'icon': 'fa-map-marker'
        }
    elif distance_km <= 50:
        if shared_skills_count > 0:
            return {
                'text': f'{shared_skills_count} shared skills',
                'subtext': f'{distance_km:.1f} km away',
                'icon': 'fa-code'
            }
        return {
            'text': 'In your area',
            'subtext': f'{distance_km:.1f} km away',
            'icon': 'fa-map-marker'
        }
    elif distance_km <= 100:
        if shared_skills_count > 0:
            return {
                'text': f'{shared_skills_count} shared skills',
                'subtext': f'{distance_km:.0f} km away',
                'icon': 'fa-code'
            }
        return {
            'text': 'Same region',
            'subtext': f'{distance_km:.0f} km away',
            'icon': 'fa-globe'
        }
    else:
        if shared_skills_count > 0:
            return {
                'text': f'{shared_skills_count} shared skills',
                'subtext': f'{distance_km:.0f} km away',
                'icon': 'fa-code'
            }
        return {
            'text': 'Suggested developer',
            'subtext': f'{distance_km:.0f} km away',
            'icon': 'fa-globe'
        }


def get_local_feed_logs(user):
    """
    Get logs for Local feed - MVP simple algorithm.
    
    Shows recent logs from nearby users within 250 KMS:
    - User must have coordinates
    - Distance must be within LOCAL_RADIUS_KM (250 km)
    - Sort logs by most recent first
    - Preserves existing local recommendation label
    """
    from logs.models import Log
    
    user_lat = user.latitude
    user_lon = user.longitude
    
    # Only show Local feed if user has coordinates
    if not user_lat or not user_lon:
        return []
    
    # Get user's skills for recommendation label
    user_skills = set(user.skills.values_list('id', flat=True)) if hasattr(user, 'skills') else set()
    
    # Fetch logs from users with coordinates
    nearby_users_logs = list(
        Log.objects
        .exclude(user=user)
        .filter(user__latitude__isnull=False, user__longitude__isnull=False)
        .select_related('user__user')
        .prefetch_related('user__skills')
        .annotate(
            reaction_count=Count('reactions', distinct=True),
            comment_count=Count('comments', distinct=True),
        )
        .order_by('-timestamp')  # Pre-sort by timestamp for efficiency
    )
    
    # Filter by distance and add metadata
    local_logs = []
    for log in nearby_users_logs:
        author_lat = log.user.latitude
        author_lon = log.user.longitude
        
        if not author_lat or not author_lon:
            continue
        
        # Calculate distance
        distance = haversine_distance(user_lat, user_lon, author_lat, author_lon)
        
        # Filter: only include logs within LOCAL_RADIUS_KM
        if distance > LOCAL_RADIUS_KM:
            continue
        
        # Calculate shared skills for recommendation label
        author_skills = set(log.user.skills.values_list('id', flat=True)) if hasattr(log.user, 'skills') else set()
        shared_count = len(user_skills.intersection(author_skills))
        
        # Add metadata
        log.distance_km = distance
        log.feed_type = 'local'
        log.is_secondary_network = False
        log.recommendation_reason = _get_local_recommendation_reason(log, distance, shared_count)
        
        local_logs.append(log)
    
    # Already sorted by timestamp (most recent first) from the query
    return local_logs


def get_network_user_ids(user):
    """
    Get IDs of users that the current user follows (primary/direct network).
    Each user has their own isolated network.
    """
    return set(
        follow.objects.filter(follower=user)
        .values_list('following_id', flat=True)
    )


def get_secondary_network_user_ids(user, primary_network_ids):
    """
    Get friends-of-friends: users followed by people the user follows,
    excluding:
    - The current user themselves
    - Users already in primary network (direct follows)
    
    This creates a secondary network unique to each user.
    """
    if not primary_network_ids:
        return set()
    
    # Users followed by people I follow
    secondary_ids = set(
        follow.objects.filter(follower_id__in=primary_network_ids)
        .exclude(following=user)  # Exclude self
        .exclude(following_id=user.id)  # Also exclude by ID
        .exclude(following_id__in=primary_network_ids)  # Exclude direct follows
        .values_list('following_id', flat=True)
    )
    return secondary_ids


def _get_secondary_recommendation_reason(log, current_user, primary_network_ids):
    """
    Generate recommendation reason for SECONDARY NETWORK logs only.
    Similar to LinkedIn/Instagram "Followed by X" or "Suggested for you" labels.
    
    Returns a dict with:
    - text: The display text (e.g., "Followed by @john")
    - subtext: Optional secondary text
    - icon: Icon class for display
    """
    log_author = log.user
    
    if not primary_network_ids:
        return {
            'text': 'Suggested for you',
            'subtext': None,
            'icon': 'fa-user-plus'
        }
    
    # Find who from user's network follows this author
    mutual_follows = follow.objects.filter(
        follower_id__in=primary_network_ids,
        following=log_author
    ).select_related('follower__user')[:3]
    
    if mutual_follows:
        names = [f.follower.user.username for f in mutual_follows]
        count = len(names)
        
        if count == 1:
            return {
                'text': f'@{names[0]} follows',
                'subtext': None,
                'icon': 'fa-user-check'
            }
        elif count == 2:
            return {
                'text': f'@{names[0]} and @{names[1]} follow',
                'subtext': None,
                'icon': 'fa-users'
            }
        else:
            # Check total count for "and X others"
            total_count = follow.objects.filter(
                follower_id__in=primary_network_ids,
                following=log_author
            ).count()
            others = total_count - 1
            return {
                'text': f'@{names[0]} and {others} others follow',
                'subtext': None,
                'icon': 'fa-users'
            }
    
    return {
        'text': 'Suggested for you',
        'subtext': 'Based on your network',
        'icon': 'fa-lightbulb-o'
    }


def get_personalized_feed(request, type='network', page=1, per_page=7, cursor=None):
    """
    Personalized feed algorithm for home page with cursor-based pagination.
    
    Feed types:
    - 'network': Logs sorted by timestamp (most recent first)
      * Primary network: direct follows
      * Secondary network: friends-of-friends
    - 'local': Logs ranked by proximity and relevance
    - 'global': Logs sorted by timestamp (most recent first)
    
    Args:
        cursor: Compound cursor "timestamp,id" for efficient pagination (None for first page)
        page: Legacy parameter for backward compatibility (ignored when cursor is used)
        per_page: Number of items to return
    
    Returns:
        Dictionary with 'items', 'next_cursor', 'has_next'
    """
    from logs.models import Log, Reaction, Comment
    from django.utils.dateparse import parse_datetime
    from django.db.models import Q
    
    user = request.user.info
    
    # Get primary network (users I follow)
    primary_network_ids = get_network_user_ids(user)
    
    # Parse compound cursor if provided (format: "timestamp,id")
    cursor_timestamp = None
    cursor_id = None
    if cursor:
        try:
            cursor_parts = cursor.split(',', 1)  # Split only on first comma
            if len(cursor_parts) == 2:
                cursor_timestamp = parse_datetime(cursor_parts[0])
                cursor_id = int(cursor_parts[1])
                # Validate that both parts were successfully parsed
                if cursor_timestamp is None or cursor_id is None:
                    cursor_timestamp = None
                    cursor_id = None
        except (ValueError, AttributeError, TypeError):
            # Invalid cursor format, ignore and start from beginning
            cursor_timestamp = None
            cursor_id = None
    
    if type == 'network':
        # NETWORK FEED: Pure recency-based sorting with cursor pagination
        # Fetches logs from both primary and secondary connections sorted by timestamp
        
        # Get secondary network IDs
        secondary_network_ids = get_secondary_network_user_ids(user, primary_network_ids)
        
        # Combine both primary and secondary network IDs
        all_network_ids = primary_network_ids | secondary_network_ids
        
        # Build query with cursor-based filtering
        query = Log.objects.filter(user_id__in=all_network_ids)
        
        if cursor_timestamp is not None and cursor_id is not None:
            # Fetch logs older than cursor using compound cursor (timestamp, id)
            # This guarantees no duplicates even when timestamps are identical
            query = query.filter(
                Q(timestamp__lt=cursor_timestamp) |
                Q(timestamp=cursor_timestamp, id__lt=cursor_id)
            )
        
        # Fetch per_page + 1 to check if there are more items
        logs_list = list(
            query
            .select_related('user__user')  # Prevent N+1 queries
            .annotate(
                reaction_count=Count('reactions', distinct=True),
                comment_count=Count('comments', distinct=True),
            )
            .order_by('-timestamp', '-id')  # Deterministic ordering: newest first, then highest ID
            [:per_page + 1]
        )
        
        # Add minimal metadata (only what's needed for display)
        primary_id_set = primary_network_ids  # Reuse set for O(1) lookup
        for log in logs_list:
            log.feed_type = 'network'
            log.is_secondary_network = log.user_id not in primary_id_set
            # Add recommendation reason ONLY for secondary network
            if log.is_secondary_network:
                log.recommendation_reason = _get_secondary_recommendation_reason(log, user, primary_network_ids)
            else:
                log.recommendation_reason = None
        
    elif type == 'global':
        # GLOBAL FEED: Pure recency-based sorting with cursor pagination
        # Simple timestamp-based sorting - most recent logs first
        
        query = Log.objects.all()
        
        if cursor_timestamp is not None and cursor_id is not None:
            # Fetch logs older than cursor using compound cursor (timestamp, id)
            # This guarantees no duplicates even when timestamps are identical
            query = query.filter(
                Q(timestamp__lt=cursor_timestamp) |
                Q(timestamp=cursor_timestamp, id__lt=cursor_id)
            )
        
        # Fetch per_page + 1 to check if there are more items
        logs_list = list(
            query
            .select_related('user__user')  # Prevent N+1 queries
            .annotate(
                reaction_count=Count('reactions', distinct=True),
                comment_count=Count('comments', distinct=True),
            )
            .order_by('-timestamp', '-id')  # Deterministic ordering: newest first, then highest ID
            [:per_page + 1]
        )
        
        # Add minimal metadata
        for log in logs_list:
            log.feed_type = 'global'
            log.is_secondary_network = False
            log.recommendation_reason = None
        
    else:
        # LOCAL FEED: Simple proximity-based filtering (within 250km) + timestamp sorting
        logs_list = get_local_feed_logs(user)
        
        # Apply cursor-based filtering for local feed using compound cursor
        if cursor_timestamp is not None and cursor_id is not None:
            logs_list = [
                log for log in logs_list 
                if log.timestamp < cursor_timestamp or 
                   (log.timestamp == cursor_timestamp and log.id < cursor_id)
            ]
        
        # Limit to per_page + 1
        logs_list = logs_list[:per_page + 1]
    
    # Cursor-based pagination logic
    has_next = len(logs_list) > per_page
    
    if has_next:
        # Remove the extra item used for has_next check
        logs_list = logs_list[:per_page]
    
    # Generate next cursor from last item (compound cursor: "timestamp,id")
    next_cursor = None
    if has_next and logs_list:
        last_item = logs_list[-1]
        next_cursor = f"{last_item.timestamp.isoformat()},{last_item.id}"
    
    # Return cursor-based response
    return {
        'items': logs_list,
        'next_cursor': next_cursor,
        'has_next': has_next,
    }

def top_skills_list():
    top_skills = list(skill.objects.all()[0:10])     # Programming Languages
    top_skills += list(skill.objects.all()[40:50])   # Frameworks and Libraries
    top_skills += list(skill.objects.all()[80:87])   # Databases
    top_skills += list(skill.objects.all()[100:103]) # Cloud Platforms
    top_skills += list(skill.objects.all()[125:127]) # Version Control
    top_skills += list(skill.objects.all()[150:152]) # Backend Frameworks
    top_skills += list(skill.objects.all()[180:182]) # AI/ML
    return top_skills