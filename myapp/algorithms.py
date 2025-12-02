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
# RECENCY MULTIPLIERS - How much to boost logs based on age
# =============================================================================
RECENCY_MULTIPLIERS = [
    (timedelta(hours=1), 10.0),     # < 1 hour: 10x boost (very fresh)
    (timedelta(hours=6), 6.0),      # 1-6 hours: 6x boost
    (timedelta(hours=24), 3.0),     # 6-24 hours: 3x boost
    (timedelta(days=3), 1.5),       # 1-3 days: 1.5x boost
    (timedelta(days=7), 0.5),       # 3-7 days: 0.5x
    (None, 0.1),                    # > 7 days: 0.1x (very old)
]

# =============================================================================
# FRESHNESS PENALTIES - Aggressive down-weight for already-interacted logs
# These are designed to push viewed content DOWN regardless of engagement
# =============================================================================
FRESHNESS_PENALTY_VIEWED = 0.15     # User has seen this log - drop to 15%
FRESHNESS_PENALTY_REACTED = 0.05    # User reacted to this log - drop to 5%
FRESHNESS_PENALTY_COMMENTED = 0.02  # User commented on this log - drop to 2%

# =============================================================================
# ENGAGEMENT SCORE CAP - Prevent high-engagement logs from dominating
# =============================================================================
ENGAGEMENT_SCORE_CAP = 10.0  # Cap engagement contribution to prevent stale popular logs

# =============================================================================
# SECONDARY NETWORK CONFIG
# =============================================================================
SECONDARY_NETWORK_RATIO = 0.25  # 25% of feed from friends-of-friends


# =============================================================================
# LOCAL FEED - RADIUS MULTIPLIERS
# =============================================================================
# (max_distance_km, multiplier) - Closer users get higher boosts
RADIUS_MULTIPLIERS = [
    (5, 10.0),      # < 5 km: 10x boost (very close)
    (20, 7.0),      # 5-20 km: 7x boost
    (50, 4.0),      # 20-50 km: 4x boost
    (100, 2.0),     # 50-100 km: 2x boost
    (None, 0.5),    # > 100 km: 0.5x (far away)
]

# Skill matching bonus for Local feed
SKILL_MATCH_BONUS = 1.5  # 1.5x multiplier for shared skills


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


def get_radius_multiplier(distance_km):
    """Get radius multiplier based on distance in kilometers."""
    if distance_km is None:
        return 0.5  # No location data
    
    for threshold, multiplier in RADIUS_MULTIPLIERS:
        if threshold is None or distance_km <= threshold:
            return multiplier
    return 0.5  # Default for very far users


def calculate_skill_match_score(user_skills, log_author_skills):
    """
    Calculate skill match bonus between current user and log author.
    Returns multiplier based on shared skills.
    """
    if not user_skills or not log_author_skills:
        return 1.0
    
    shared_skills = user_skills.intersection(log_author_skills)
    if shared_skills:
        # More shared skills = higher bonus, capped at 2.0
        bonus = 1.0 + (len(shared_skills) * 0.2)
        return min(bonus, 2.0)
    return 1.0


def calculate_local_log_score(log, user, distance_km, user_skills, viewed_log_ids, reacted_log_ids, commented_log_ids):
    """
    Calculate score for Local feed with radius-based ranking.
    
    FORMULA: Score = (radius_multiplier × recency_multiplier × skill_bonus) + (capped_engagement × freshness)
    
    This ensures:
    - Nearby users rank MUCH higher than distant users
    - Recency still matters significantly
    - Skill overlap provides a bonus
    - Viewed content drops significantly
    """
    # Get author's skills
    log_author_skills = set(log.user.skills.values_list('id', flat=True)) if hasattr(log.user, 'skills') else set()
    
    # Radius multiplier - PRIMARY factor for local feed
    radius = get_radius_multiplier(distance_km)
    
    # Recency multiplier
    recency = get_recency_multiplier(log.timestamp)
    
    # Skill match bonus
    skill_bonus = calculate_skill_match_score(user_skills, log_author_skills)
    
    # Base engagement (capped)
    engagement_score = calculate_engagement_score(log)
    
    # Freshness penalty
    freshness, interaction_type = get_interaction_status(
        log.id, viewed_log_ids, reacted_log_ids, commented_log_ids
    )
    
    # Store for display
    log.user_interaction = interaction_type
    log.distance_km = distance_km
    
    # LOCAL SCORING FORMULA: Radius × Recency × Skill, plus engagement bonus
    # Primary score: radius * recency * skill (0-200 range)
    primary_score = radius * recency * skill_bonus
    
    # Engagement bonus (reduced by freshness penalty)
    engagement_bonus = engagement_score * freshness
    
    # If user has interacted, penalize primary score too
    if interaction_type:
        primary_score *= freshness
    
    return primary_score + engagement_bonus


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


def get_local_feed_logs(user, base_queryset, per_page, viewed_log_ids, reacted_log_ids, commented_log_ids):
    """
    Get logs for Local feed ranked by proximity and relevance.
    
    Strategy:
    1. If user has coordinates, use haversine distance
    2. If no coordinates, fall back to same city/state/country
    3. Include skill-based suggestions even if far away
    """
    user_lat = user.latitude
    user_lon = user.longitude
    user_skills = set(user.skills.values_list('id', flat=True)) if hasattr(user, 'skills') else set()
    
    # Get all users with location data, excluding current user
    candidate_logs = []
    
    if user_lat and user_lon:
        # User has coordinates - use distance-based ranking
        # Fetch logs from users who have coordinates
        nearby_logs = list(
            base_queryset.exclude(user=user)
            .filter(user__latitude__isnull=False, user__longitude__isnull=False)
            .select_related('user__user')
            .order_by('-timestamp')[:per_page * 5]
        )
        
        # Calculate distances and score each log
        for log in nearby_logs:
            author_lat = log.user.latitude
            author_lon = log.user.longitude
            
            if author_lat and author_lon:
                distance = haversine_distance(user_lat, user_lon, author_lat, author_lon)
            else:
                distance = None
            
            score = calculate_local_log_score(
                log, user, distance, user_skills,
                viewed_log_ids, reacted_log_ids, commented_log_ids
            )
            
            # Calculate shared skills for recommendation label
            author_skills = set(log.user.skills.values_list('id', flat=True)) if hasattr(log.user, 'skills') else set()
            shared_count = len(user_skills.intersection(author_skills))
            
            log.feed_score = score
            log.feed_type = 'local'
            log.is_secondary_network = False
            log.recommendation_reason = _get_local_recommendation_reason(log, distance, shared_count)
            candidate_logs.append((score, random.random(), log))
    
    # Fallback: Include logs from same city/state/country (for users without coordinates)
    fallback_filters = []
    if user.city:
        fallback_filters.append(Q(user__city__iexact=user.city))
    if user.state:
        fallback_filters.append(Q(user__state__iexact=user.state))
    if user.country:
        fallback_filters.append(Q(user__country__iexact=user.country))
    
    if fallback_filters:
        # Combine with OR
        fallback_query = fallback_filters[0]
        for f in fallback_filters[1:]:
            fallback_query |= f
        
        # Get logs from same region (excluding already fetched)
        existing_log_ids = {log.id for _, _, log in candidate_logs}
        
        region_logs = list(
            base_queryset.exclude(user=user)
            .exclude(id__in=existing_log_ids)
            .filter(fallback_query)
            .select_related('user__user')
            .order_by('-timestamp')[:per_page * 3]
        )
        
        for log in region_logs:
            # No coordinates, estimate based on matching fields
            if log.user.city and user.city and log.user.city.lower() == user.city.lower():
                distance = 10  # Same city ~ 10km estimate
            elif log.user.state and user.state and log.user.state.lower() == user.state.lower():
                distance = 50  # Same state ~ 50km estimate
            else:
                distance = 150  # Same country ~ 150km estimate
            
            score = calculate_local_log_score(
                log, user, distance, user_skills,
                viewed_log_ids, reacted_log_ids, commented_log_ids
            )
            
            author_skills = set(log.user.skills.values_list('id', flat=True)) if hasattr(log.user, 'skills') else set()
            shared_count = len(user_skills.intersection(author_skills))
            
            log.feed_score = score
            log.feed_type = 'local'
            log.is_secondary_network = False
            log.recommendation_reason = _get_local_recommendation_reason(log, distance, shared_count)
            candidate_logs.append((score, random.random(), log))
    
    # Sort by score and deduplicate
    candidate_logs.sort(key=lambda x: (-x[0], x[1]))
    
    # DEBUG: Print local scores
    print("\n" + "="*60)
    print(f"LOCAL FEED SCORES FOR USER: {user.user.username}")
    print("="*60)
    for score, _, log in candidate_logs[:20]:
        dist = getattr(log, 'distance_km', '?')
        if isinstance(dist, (int, float)):
            dist_str = f"{dist:.1f}km"
        else:
            dist_str = "N/A"
        print(f"({log.sig} by @{log.user.user.username}) - Score: {score:.2f}, Distance: {dist_str}")
    print("="*60 + "\n")
    
    seen_ids = set()
    unique_logs = []
    for _, _, log in candidate_logs:
        if log.id not in seen_ids:
            seen_ids.add(log.id)
            unique_logs.append(log)
    
    return unique_logs


def get_recency_multiplier(log_timestamp):
    """Calculate recency multiplier based on log age."""
    age = now() - log_timestamp
    for threshold, multiplier in RECENCY_MULTIPLIERS:
        if threshold is None or age <= threshold:
            return multiplier
    return 0.2  # Default for very old logs


def calculate_engagement_score(log):
    """
    Calculate base engagement score for a log.
    Formula: reactions * 1.5 + comments * 2.0 + views * 0.1
    Capped at ENGAGEMENT_SCORE_CAP to prevent high-engagement logs from dominating.
    """
    reaction_count = getattr(log, 'reaction_count', 0) or 0
    comment_count = getattr(log, 'comment_count', 0) or 0
    view_count = getattr(log, 'total_views', 0) or 0
    
    raw_score = (reaction_count * 1.5) + (comment_count * 2.0) + (view_count * 0.1)
    # Cap engagement to prevent popular logs from staying at top forever
    return min(raw_score, ENGAGEMENT_SCORE_CAP)


def get_interaction_status(log_id, viewed_log_ids, reacted_log_ids, commented_log_ids):
    """
    Get the interaction status and corresponding penalty for a log.
    Returns (penalty, interaction_type) tuple.
    """
    if log_id in commented_log_ids:
        return (FRESHNESS_PENALTY_COMMENTED, 'commented')
    elif log_id in reacted_log_ids:
        return (FRESHNESS_PENALTY_REACTED, 'reacted')
    elif log_id in viewed_log_ids:
        return (FRESHNESS_PENALTY_VIEWED, 'viewed')
    return (1.0, None)


def calculate_log_score(log, user, viewed_log_ids, reacted_log_ids, commented_log_ids, is_secondary=False):
    """
    Calculate final score for a log using a RECENCY-FIRST formula.
    
    NEW FORMULA (recency dominates):
    Score = (recency_multiplier * 10) + (capped_engagement * freshness_penalty)
    
    This ensures:
    - Fresh unseen logs ALWAYS rank higher than old seen logs
    - Engagement only matters for tie-breaking among similar-age logs
    - Viewed/interacted logs drop significantly regardless of engagement
    
    If is_secondary (friend-of-friend), apply additional 0.7x multiplier
    """
    # Base engagement (capped to prevent domination)
    engagement_score = calculate_engagement_score(log)
    
    # Recency boost - THIS IS THE PRIMARY RANKING FACTOR
    recency = get_recency_multiplier(log.timestamp)
    
    # Freshness penalty based on deepest interaction
    freshness, interaction_type = get_interaction_status(
        log.id, viewed_log_ids, reacted_log_ids, commented_log_ids
    )
    
    # Store interaction type for recommendation labels
    log.user_interaction = interaction_type
    
    # NEW SCORING FORMULA: Recency is primary, engagement is secondary
    # Recency score: dominates ranking (0-100 range)
    recency_score = recency * 10
    
    # Engagement bonus: only affects similar-recency logs (0-10 range, reduced by freshness)
    engagement_bonus = engagement_score * freshness
    
    # If user has interacted, HEAVILY penalize the recency score too
    if interaction_type:
        recency_score *= freshness
    
    # Final score
    score = recency_score + engagement_bonus
    
    # Secondary network gets lower priority than direct network
    if is_secondary:
        score *= 0.7
    
    return score


def get_user_interaction_sets(user):
    """
    Get sets of log IDs that the user has interacted with.
    Used for calculating freshness penalties.
    
    Returns three sets for each user (isolated per user):
    - viewed_log_ids: Logs the user has viewed
    - reacted_log_ids: Logs the user has reacted to
    - commented_log_ids: Logs the user has commented OR replied on
    """
    from logs.models import LogViews, Reaction, Comment
    
    # Logs viewed by this specific user
    viewed_log_ids = set(
        LogViews.objects.filter(user=user)
        .values_list('log_id', flat=True)
    )
    
    # Logs this specific user has reacted to
    reacted_log_ids = set(
        Reaction.objects.filter(user=user)
        .values_list('mindlog_id', flat=True)
    )
    
    # Logs this specific user has commented on (includes replies)
    # Both top-level comments and replies have mindlog_id pointing to the log
    commented_log_ids = set(
        Comment.objects.filter(user=user)
        .values_list('mindlog_id', flat=True)
    )
    
    return viewed_log_ids, reacted_log_ids, commented_log_ids


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
    Advanced personalized feed algorithm with recency boost and freshness penalties.
    
    Feed types:
    - 'network': Logs from followed users + secondary network suggestions
    - 'local': Logs from same location/organization (future)
    - 'global': All logs, globally ranked
    
    Scoring Formula:
    Score = (engagement_score + 1) * recency_multiplier * freshness_penalty
    
    Where:
    - engagement_score = reactions * 1.5 + comments * 2.0 + views * 0.1
    - recency_multiplier = 5.0 (< 1hr) to 0.2 (> 7 days)
    - freshness_penalty = 0.3 (viewed), 0.1 (reacted), 0.05 (commented)
    """
    from logs.models import Log, Reaction, Comment
    
    user = request.user.info
    
    # Get user interaction history for freshness calculation
    viewed_log_ids, reacted_log_ids, commented_log_ids = get_user_interaction_sets(user)
    
    # Get primary network (users I follow)
    primary_network_ids = get_network_user_ids(user)
    
    # Base queryset with annotations for engagement metrics
    base_queryset = Log.objects.select_related('user__user').annotate(
        reaction_count=Count('reactions', distinct=True),
        comment_count=Count('comments', distinct=True),
    )
    
    if type == 'network':
        # NETWORK FEED: Logs from followed users + secondary network
        
        # Primary network logs (70-80% of feed)
        primary_logs = list(
            base_queryset.filter(user_id__in=primary_network_ids)
            .order_by('-timestamp')[:per_page * 3]  # Fetch extra for scoring
        )
        
        # Secondary network logs (20-30% of feed)
        secondary_network_ids = get_secondary_network_user_ids(user, primary_network_ids)
        secondary_logs = list(
            base_queryset.filter(user_id__in=secondary_network_ids)
            .order_by('-timestamp')[:per_page * 2]
        )
        
        # Score all logs - only secondary network gets recommendation labels
        scored_logs = []
        for log in primary_logs:
            score = calculate_log_score(
                log, user, viewed_log_ids, reacted_log_ids, commented_log_ids,
                is_secondary=False
            )
            log.feed_score = score
            log.feed_type = 'network'
            log.is_secondary_network = False
            log.recommendation_reason = None  # No label for primary network
            scored_logs.append((score, random.random(), log))  # Random for tie-breaking
        
        for log in secondary_logs:
            score = calculate_log_score(
                log, user, viewed_log_ids, reacted_log_ids, commented_log_ids,
                is_secondary=True
            )
            log.feed_score = score
            log.feed_type = 'network'
            log.is_secondary_network = True
            # Add recommendation reason ONLY for secondary network (suggested posts)
            log.recommendation_reason = _get_secondary_recommendation_reason(log, user, primary_network_ids)
            scored_logs.append((score, random.random(), log))
        
        # Sort by score (descending) and get unique logs
        scored_logs.sort(key=lambda x: (-x[0], x[1]))
        
        # DEBUG: Print scores for verification
        print("\n" + "="*60)
        print(f"FEED SCORES FOR USER: {user.user.username}")
        print("="*60)
        for score, _, log in scored_logs:
            network_type = "SECONDARY" if log.is_secondary_network else "PRIMARY"
            print(f"({log.sig} by @{log.user.user.username} [{network_type}]) - Score: {score:.2f}")
        print("="*60 + "\n")
        
        # Deduplicate (same log might appear from multiple paths)
        seen_ids = set()
        unique_logs = []
        for _, _, log in scored_logs:
            if log.id not in seen_ids:
                seen_ids.add(log.id)
                unique_logs.append(log)
        
        logs_list = unique_logs
        
    elif type == 'global':
        # GLOBAL FEED: All logs, globally ranked
        all_logs = list(
            base_queryset.exclude(user=user)
            .order_by('-timestamp')[:per_page * 5]
        )
        
        scored_logs = []
        for log in all_logs:
            score = calculate_log_score(
                log, user, viewed_log_ids, reacted_log_ids, commented_log_ids,
                is_secondary=False
            )
            log.feed_score = score
            log.feed_type = 'global'
            log.is_secondary_network = False
            scored_logs.append((score, random.random(), log))
        
        scored_logs.sort(key=lambda x: (-x[0], x[1]))
        logs_list = [log for _, _, log in scored_logs]
        
    else:
        # LOCAL FEED: Proximity-based ranking with skill matching
        logs_list = get_local_feed_logs(
            user, base_queryset, per_page,
            viewed_log_ids, reacted_log_ids, commented_log_ids
        )
    
    # Pagination
    paginator = Paginator(logs_list, per_page)
    try:
        page_obj = paginator.page(page)
    except EmptyPage:
        # Return empty page object
        return paginator.get_page(paginator.num_pages)
    
    return page_obj

def top_skills_list():
    top_skills = list(skill.objects.all()[0:10])     # Programming Languages
    top_skills += list(skill.objects.all()[40:50])   # Frameworks and Libraries
    top_skills += list(skill.objects.all()[80:87])   # Databases
    top_skills += list(skill.objects.all()[100:103]) # Cloud Platforms
    top_skills += list(skill.objects.all()[125:127]) # Version Control
    top_skills += list(skill.objects.all()[150:152]) # Backend Frameworks
    top_skills += list(skill.objects.all()[180:182]) # AI/ML
    return top_skills