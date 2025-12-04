"""
Nearby Developers Feature
Identifies and ranks geographically closest developers to a user for the Local tab.
Includes diversity filtering to ensure varied results.
"""
from django.db.models import Q, Count, Prefetch
from django.core.cache import cache
from myapp.models import userinfo, follow
from myapp.algorithms import haversine_distance
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)

# Configuration
MAX_DISTANCE_KM = 500  # Maximum distance to consider (km)
CACHE_TTL_SECONDS = 600  # Cache results for 10 minutes


def get_nearby_developers(user, limit=5, exclude_following=False):
    """
    Get geographically closest developers to a user.
    
    Args:
        user: userinfo object or User object
        limit: Number of developers to return (default 5)
        exclude_following: Whether to exclude users already being followed
    
    Returns:
        List of tuples: [(userinfo_obj, distance_km), ...]
    """
    # Get userinfo if User object is passed
    if hasattr(user, 'info'):
        user = user.info
    
    # Check if user has coordinates
    if not user.latitude or not user.longitude:
        logger.debug(f'User {user.id} has no coordinates, returning empty list')
        return []
    
    user_lat = float(user.latitude)
    user_lon = float(user.longitude)
    
    # Try cache first
    cache_key = f'nearby_devs:{user.id}:{limit}:{exclude_following}'
    cached = cache.get(cache_key)
    if cached:
        logger.debug(f'Cache hit for nearby developers: user {user.id}')
        return cached
    
    # Get candidate pool - users with coordinates
    candidates = _get_candidate_pool(user, exclude_following)
    
    # Calculate distances
    scored_candidates = []
    for candidate in candidates:
        if not candidate.latitude or not candidate.longitude:
            continue
        
        distance = haversine_distance(
            user_lat, user_lon,
            float(candidate.latitude), float(candidate.longitude)
        )
        
        # Skip if too far
        if distance > MAX_DISTANCE_KM:
            continue
        
        scored_candidates.append((candidate, distance))
    
    # Sort by distance (ascending - closest first)
    scored_candidates.sort(key=lambda x: x[1])
    
    # Apply diversity filter
    diverse_results = _apply_diversity_filter(scored_candidates, limit * 3)
    
    # Take top results
    results = diverse_results[:limit]
    
    # Cache results
    cache.set(cache_key, results, CACHE_TTL_SECONDS)
    
    logger.info(f'Found {len(results)} nearby developers for user {user.id}')
    return results


def _get_candidate_pool(user, exclude_following=False):
    """
    Get pool of candidate developers with coordinates.
    """
    # Base queryset - exclude self, only users with coordinates
    candidates = userinfo.objects.exclude(id=user.id).filter(
        user__is_active=True,
        latitude__isnull=False,
        longitude__isnull=False
    ).select_related(
        'user',
        'coding_style'
    ).prefetch_related(
        'skills'
    )
    
    # Optionally exclude already following
    if exclude_following:
        following_ids = follow.objects.filter(
            follower=user
        ).values_list('following_id', flat=True)
        candidates = candidates.exclude(id__in=following_ids)
    
    # Limit candidate pool for performance
    return candidates[:200]


def _apply_diversity_filter(scored_candidates, target_count):
    """
    Apply diversity filtering to ensure varied results.
    
    Diversity factors:
    1. Coding style diversity - avoid multiple devs with same coding style
    2. City diversity - avoid multiple devs from exact same city
    """
    if not scored_candidates:
        return []
    
    diverse_results = []
    seen_coding_styles = {}  # coding_style_id -> count
    seen_cities = {}  # city -> count
    MAX_PER_STYLE = 2  # Max developers per coding style
    MAX_PER_CITY = 2  # Max developers per city
    
    for candidate, distance in scored_candidates:
        # Check coding style diversity
        style_id = candidate.coding_style_id if candidate.coding_style else None
        style_count = seen_coding_styles.get(style_id, 0)
        
        # Check city diversity
        city = candidate.city.lower() if candidate.city else None
        city_count = seen_cities.get(city, 0) if city else 0
        
        # Calculate diversity penalty (higher = less diverse)
        diversity_penalty = 0
        if style_id and style_count >= MAX_PER_STYLE:
            diversity_penalty += 1
        if city and city_count >= MAX_PER_CITY:
            diversity_penalty += 1
        
        # Skip if too repetitive (unless we have very few results)
        if diversity_penalty >= 2 and len(diverse_results) >= 3:
            continue
        
        # Add to results
        diverse_results.append((candidate, distance))
        
        # Update counters
        if style_id:
            seen_coding_styles[style_id] = style_count + 1
        if city:
            seen_cities[city] = city_count + 1
        
        if len(diverse_results) >= target_count:
            break
    
    return diverse_results


def invalidate_nearby_cache(user):
    """
    Invalidate nearby developers cache for a user.
    Called when user's location changes.
    """
    if hasattr(user, 'info'):
        user = user.info
    
    # Clear all variants of the cache
    for limit in [5, 10]:
        for exclude in [True, False]:
            cache_key = f'nearby_devs:{user.id}:{limit}:{exclude}'
            cache.delete(cache_key)
    
    logger.debug(f'Invalidated nearby developers cache for user {user.id}')
