"""
Developer Recommendation System
Provides personalized developer recommendations based on multiple factors
"""
from django.db.models import Count, Q, F, Prefetch, Value, IntegerField
from django.db.models.functions import Coalesce
from django.core.cache import cache
from django.utils import timezone
from datetime import timedelta
from myapp.models import userinfo, follow
import logging

logger = logging.getLogger(__name__)


def get_recommended_developers(user, limit=10, exclude_following=True, use_cache=True):
    """
    Get personalized developer recommendations for a user
    
    Args:
        user: userinfo object or User object
        limit: Number of recommendations to return (default 10)
        exclude_following: Exclude users already being followed (default True)
        use_cache: Use cached results if available (default True)
    
    Returns:
        List of tuples: [(userinfo_obj, score, reason), ...]
    """
    # Get userinfo if User object is passed
    if hasattr(user, 'info'):
        user = user.info
    
    # Try cache first
    if use_cache:
        cache_key = f'dev_recommendations:{user.id}'
        cached = cache.get(cache_key)
        if cached:
            logger.info(f'Cache hit for user {user.id}')
            return cached[:limit]
    
    # Get candidate pool
    candidates = _get_candidate_pool(user, exclude_following)
    
    # Score each candidate
    scored_candidates = []
    for candidate in candidates:
        score, reason = _calculate_recommendation_score(user, candidate)
        if score > 0:  # Only include if there's some match
            scored_candidates.append((candidate, score, reason))
    
    # Sort by score (descending) and add diversity
    scored_candidates.sort(key=lambda x: x[1], reverse=True)
    
    # Apply diversity filter
    diverse_recommendations = _apply_diversity(scored_candidates, limit * 2)
    
    # Cache results
    if use_cache:
        cache.set(cache_key, diverse_recommendations, 3600)  # 1 hour TTL
    
    logger.info(f'Generated {len(diverse_recommendations)} recommendations for user {user.id}')
    
    return diverse_recommendations[:limit]


def _get_candidate_pool(user, exclude_following=True):
    """
    Get pool of candidate developers to recommend
    
    Strategy:
    1. Same coding style users
    2. Same location users
    3. Users with mutual connections
    4. Active users
    
    Optimized with select_related and prefetch_related
    """
    # Base queryset - exclude self
    candidates = userinfo.objects.exclude(id=user.id).filter(
        user__is_active=True
    ).select_related(
        'user',
        'coding_style'
    ).prefetch_related(
        Prefetch('followers', queryset=follow.objects.select_related('follower')),
        Prefetch('following', queryset=follow.objects.select_related('following'))
    )
    
    # Exclude already following
    if exclude_following:
        following_ids = user.following.values_list('following_id', flat=True)
        candidates = candidates.exclude(id__in=following_ids)
    
    # Prioritize users with some commonality
    base_filters = Q(coding_style=user.coding_style) | \
                   Q(city=user.city) | \
                   Q(state=user.state)
    
    # Get users with commonality first (up to 200)
    priority_candidates = list(candidates.filter(base_filters)[:200])
    
    # Add some random diverse candidates (up to 50)
    diverse_candidates = list(candidates.exclude(
        id__in=[c.id for c in priority_candidates]
    ).order_by('?')[:50])
    
    return priority_candidates + diverse_candidates


def _calculate_recommendation_score(current_user, candidate):
    """
    Calculate recommendation score based on multiple factors
    
    Returns:
        (score, reason_text) tuple
    """
    score = 0
    reasons = []
    
    # 1. Coding Style Match (25 points)
    if candidate.coding_style and current_user.coding_style:
        if candidate.coding_style == current_user.coding_style:
            score += 25
            reasons.append(f"Same coding style: {candidate.coding_style.name}")
    
    # 2. Location Proximity (15 points)
    if candidate.city and current_user.city:
        if candidate.city == current_user.city:
            score += 15
            reasons.append(f"From {candidate.city}")
        elif candidate.state == current_user.state:
            score += 10
            reasons.append(f"From {candidate.state}")
        elif candidate.country == current_user.country:
            score += 5
    
    # 3. Mutual Connections (20 points)
    mutual_count = _get_mutual_connections_count(current_user, candidate)
    if mutual_count > 0:
        mutual_score = min(mutual_count * 5, 20)
        score += mutual_score
        reasons.append(f"{mutual_count} mutual connection{'s' if mutual_count > 1 else ''}")
    
    # 4. Activity Similarity (15 points)
    if _is_active_user(candidate):
        score += 15
        reasons.append("Active developer")
    
    # 5. Profile Completeness (10 points)
    if _is_profile_complete(candidate):
        score += 10
    
    # 6. Recent Activity (10 points)
    if _is_recently_active(candidate):
        score += 10
    
    # 7. Follower/Following Ratio (5 points)
    if _has_balanced_network(candidate):
        score += 5
    
    # Generate reason text
    reason_text = reasons[0] if reasons else "Suggested for you"
    
    return min(score, 100), reason_text


def _get_mutual_connections_count(user1, user2):
    """
    Count mutual connections between two users
    Uses prefetched data to avoid N+1 queries
    """
    # Get user1's following
    user1_following = set(user1.following.values_list('following_id', flat=True))
    
    # Get user2's following
    user2_following = set(user2.following.values_list('following_id', flat=True))
    
    # Count intersection
    return len(user1_following & user2_following)


def _is_active_user(user):
    """Check if user is active (has logs in last 30 days)"""
    if not hasattr(user, '_activity_checked'):
        from logs.models import Log
        thirty_days_ago = timezone.now() - timedelta(days=30)
        user._is_active = Log.objects.filter(
            user=user,
            timestamp__gte=thirty_days_ago
        ).exists()
        user._activity_checked = True
    return getattr(user, '_is_active', False)


def _is_profile_complete(user):
    """Check if profile has key fields filled"""
    return all([
        user.bio,
        user.city,
        user.coding_style,
        user.profile_image
    ])


def _is_recently_active(user):
    """Check if user was active in last 7 days"""
    if user.user.last_login:
        seven_days_ago = timezone.now() - timedelta(days=7)
        return user.user.last_login >= seven_days_ago
    return False


def _has_balanced_network(user):
    """Check if user has a balanced follower/following ratio"""
    follower_count = user.followers.count()
    following_count = user.following.count()
    
    if following_count == 0:
        return follower_count < 100  # Not a spam account
    
    ratio = follower_count / following_count
    return 0.5 <= ratio <= 2.0  # Reasonable ratio


def _apply_diversity(scored_candidates, limit):
    """
    Apply diversity to recommendations to avoid echo chamber
    Ensures variety in coding styles, locations, etc.
    """
    if len(scored_candidates) <= limit:
        return scored_candidates
    
    diverse_list = []
    seen_coding_styles = set()
    seen_cities = set()
    
    # First pass: pick diverse candidates with high scores
    for candidate, score, reason in scored_candidates:
        if len(diverse_list) >= limit:
            break
        
        coding_style = candidate.coding_style.id if candidate.coding_style else None
        city = candidate.city
        
        # Prefer candidates with unseen attributes
        is_diverse = (coding_style not in seen_coding_styles) or (city not in seen_cities)
        
        if is_diverse or len(diverse_list) < limit // 2:
            diverse_list.append((candidate, score, reason))
            if coding_style:
                seen_coding_styles.add(coding_style)
            if city:
                seen_cities.add(city)
    
    # Second pass: fill remaining slots with highest scores
    for candidate, score, reason in scored_candidates:
        if len(diverse_list) >= limit:
            break
        if (candidate, score, reason) not in diverse_list:
            diverse_list.append((candidate, score, reason))
    
    return diverse_list


def invalidate_recommendation_cache(user):
    """
    Invalidate recommendation cache for a user
    Call this after follow/unfollow actions
    """
    if hasattr(user, 'info'):
        user = user.info
    
    cache_key = f'dev_recommendations:{user.id}'
    cache.delete(cache_key)
    logger.info(f'Invalidated recommendation cache for user {user.id}')
