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
# RECENCY MULTIPLIERS - Used by Local and Global feeds
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
# FRESHNESS PENALTIES - Used by Local and Global feeds
# =============================================================================
FRESHNESS_PENALTY_VIEWED = 0.15     # User has seen this log - drop to 15%
FRESHNESS_PENALTY_REACTED = 0.05    # User reacted to this log - drop to 5%
FRESHNESS_PENALTY_COMMENTED = 0.02  # User commented on this log - drop to 2%

# =============================================================================
# ENGAGEMENT SCORE CAP - Used by Local feed
# =============================================================================
ENGAGEMENT_SCORE_CAP = 10.0  # Cap engagement contribution to prevent stale popular logs


# =============================================================================
# LOCAL FEED - RADIUS MULTIPLIERS (DISTANCE IS PRIMARY)
# =============================================================================
# (max_distance_km, multiplier) - Closer users get SIGNIFICANTLY higher boosts
# Distance is the PRIMARY ranking factor - these multipliers create hard tiers
RADIUS_MULTIPLIERS = [
    (5, 100.0),     # < 5 km: 100x boost (VERY CLOSE - top priority)
    (20, 50.0),     # 5-20 km: 50x boost
    (50, 20.0),     # 20-50 km: 20x boost
    (100, 5.0),     # 50-100 km: 5x boost
    (None, 1.0),    # > 100 km: 1x (baseline, far away)
]

# Recency multiplier reduction for Local feed (compared to Network feed)
# Only applies significant recency boost for NEARBY users (<25km)
LOCAL_RECENCY_DAMPENER = 0.3  # Reduce recency impact by 70%
NEARBY_RECENCY_BOOST = 2.0  # Extra recency boost for <25km users
NEARBY_THRESHOLD_KM = 25  # Distance threshold for recency priority

# Skill matching bonus for Local feed
SKILL_MATCH_BONUS = 1.5  # 1.5x multiplier for shared skills

# Noise control - reduced randomness for Local feed
LOCAL_NOISE_FACTOR = 0.001  # Minimal noise to break exact ties only


# =============================================================================
# GLOBAL FEED CONFIGURATION
# =============================================================================
# Ranking weight distribution (must sum to 1.0)
GLOBAL_WEIGHTS = {
    'quality': 0.35,        # 35% - Content quality signals
    'trending': 0.25,       # 25% - Current momentum/virality
    'personalization': 0.20,  # 20% - User interest alignment
    'recency': 0.12,        # 12% - Freshness factor
    'diversity': 0.08,      # 8% - Feed variety bonus
}

# Global feed exclusion distance (km)
GLOBAL_NEARBY_EXCLUSION_KM = 100  # Exclude logs from <100km (visible in Local tab)

# Trending window configuration
TRENDING_WINDOW_HOURS = 24  # Consider engagement in last 24 hours for trending
TRENDING_VELOCITY_WEIGHT = 2.0  # How much to weight recent engagement velocity

# Diversity controls
MAX_LOGS_PER_AUTHOR = 2  # Max logs from same author per page
DIVERSITY_SKILL_BONUS = 0.15  # Bonus for introducing new skill categories
DIVERSITY_TIME_SPREAD_BONUS = 0.1  # Bonus for time diversity

# Quality score thresholds
MIN_CONTENT_LENGTH = 20  # Minimum characters for quality bonus
QUALITY_CODE_BONUS = 0.3  # Bonus for logs with code snippets
QUALITY_IMAGE_BONUS = 0.2  # Bonus for logs with images
QUALITY_LINK_BONUS = 0.1  # Bonus for logs with links

# Engagement penalty for already-interacted content in Global feed
GLOBAL_INTERACTION_PENALTIES = {
    'viewed': 0.10,     # Drop to 10% (aggressive - we want fresh content)
    'reacted': 0.03,    # Drop to 3%
    'commented': 0.01,  # Drop to 1% (virtually hidden)
}


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
    Calculate score for Local feed with DISTANCE-FIRST ranking.
    
    NEW FORMULA (distance dominates):
    Score = radius_multiplier × (1 + dampened_recency + skill_bonus) × freshness
    
    Key principles:
    1. DISTANCE IS PRIMARY - Radius multiplier creates hard tiers (100x, 50x, 20x, 5x, 1x)
    2. RECENCY IS SECONDARY - Dampened by 70%, only significant for <25km users
    3. SKILL BONUS - Small additive bonus for shared skills
    4. FRESHNESS - Penalizes viewed/interacted content (viewed: 15%, reacted: 5%, commented: 2%)
    
    This ensures:
    - A 5km user will ALWAYS rank above a 50km user (100x vs 20x base)
    - Within same distance tier, recency breaks ties
    - Nearby users (<25km) get extra recency priority
    - Already viewed/interacted logs are significantly penalized
    """
    # Get author's skills
    log_author_skills = set(log.user.skills.values_list('id', flat=True)) if hasattr(log.user, 'skills') else set()
    
    # 1. RADIUS MULTIPLIER - PRIMARY factor (creates hard distance tiers)
    radius = get_radius_multiplier(distance_km)
    
    # 2. RECENCY - Secondary factor, dampened for Local feed
    raw_recency = get_recency_multiplier(log.timestamp)
    # Dampen recency so it doesn't override distance tiers
    dampened_recency = raw_recency * LOCAL_RECENCY_DAMPENER
    
    # 3. NEARBY BONUS - Extra recency boost for users within 25km
    # This makes recency matter more among nearby users
    is_nearby = distance_km is not None and distance_km <= NEARBY_THRESHOLD_KM
    if is_nearby:
        dampened_recency *= NEARBY_RECENCY_BOOST
    
    # 4. SKILL MATCH BONUS - Small additive bonus
    skill_bonus = calculate_skill_match_score(user_skills, log_author_skills)
    # Convert to additive (0.0 to 0.5 range)
    skill_additive = (skill_bonus - 1.0) * 0.5
    
    # 5. ENGAGEMENT - Minor factor (capped)
    engagement_score = calculate_engagement_score(log)
    # Normalize engagement to 0-0.5 range
    engagement_additive = min(engagement_score / 20.0, 0.5)
    
    # 6. FRESHNESS PENALTY
    freshness, interaction_type = get_interaction_status(
        log.id, viewed_log_ids, reacted_log_ids, commented_log_ids
    )
    
    # Store for display
    log.user_interaction = interaction_type
    log.distance_km = distance_km
    
    # FINAL SCORING FORMULA:
    # Base: radius (creates tiers)
    # Multiplied by: (1 + recency + skill + engagement) to break ties within tiers
    # Then: freshness penalty for viewed content
    secondary_factors = 1.0 + dampened_recency + skill_additive + engagement_additive
    score = radius * secondary_factors * freshness
    
    return score


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
    - Only include logs from users with GPS coordinates
    - Use haversine distance for precise geographic ranking
    - Users without coordinates will see an empty Local feed
    """
    user_lat = user.latitude
    user_lon = user.longitude
    user_skills = set(user.skills.values_list('id', flat=True)) if hasattr(user, 'skills') else set()
    
    candidate_logs = []
    
    # Only show Local feed if user has coordinates
    if not user_lat or not user_lon:
        return []
    
    # Fetch logs only from users who have coordinates
    nearby_logs = list(
        base_queryset.exclude(user=user)
        .filter(user__latitude__isnull=False, user__longitude__isnull=False)
        .select_related('user__user')
        .order_by('-timestamp')[:500]  # Fixed limit for consistent coverage
    )
    
    # Calculate distances and score each log
    for log in nearby_logs:
        author_lat = log.user.latitude
        author_lon = log.user.longitude
        
        if author_lat and author_lon:
            distance = haversine_distance(user_lat, user_lon, author_lat, author_lon)
        else:
            continue  # Skip logs without coordinates
        
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
        # Use minimal noise for tie-breaking only (controlled randomness)
        noise = random.random() * LOCAL_NOISE_FACTOR
        candidate_logs.append((score, noise, log))
    
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


# =============================================================================
# GLOBAL FEED ALGORITHM
# =============================================================================
# 
# Ranking Formula: Score = Σ(weight_i × component_i) × interaction_penalty
# 
# Components:
# 1. Quality (35%): Content richness signals (code, images, links, length)
# 2. Trending (25%): Recent engagement velocity
# 3. Personalization (20%): Skill/interest alignment
# 4. Recency (12%): Time-based freshness
# 5. Diversity (8%): Feed variety bonus
#
# Exclusions:
# - Primary network (direct follows) - visible in Network tab
# - Secondary network (friends-of-friends) - visible in Network tab
# - Nearby users (<100km) - visible in Local tab
# - User's own logs
#
# =============================================================================


def calculate_quality_score(log):
    """
    Calculate content quality score (0.0 to 1.0).
    
    Quality signals:
    - Content length (longer = more thoughtful)
    - Has code snippet (valuable technical content)
    - Has image/snapshot (visual content)
    - Has link (references/sources)
    
    Returns normalized score between 0 and 1.
    """
    score = 0.0
    
    # Content length scoring
    content = log.content or ''
    content_length = len(content)
    if content_length >= MIN_CONTENT_LENGTH:
        # Logarithmic scaling: longer content gets diminishing returns
        # 20 chars = 0.1, 50 chars = 0.2, 100 chars = 0.3, 200+ chars = 0.4
        length_score = min(0.4, 0.1 * math.log2(content_length / MIN_CONTENT_LENGTH + 1))
        score += length_score
    
    # Code snippet bonus (valuable technical content)
    if log.code_snippet:
        score += QUALITY_CODE_BONUS
    
    # Image/snapshot bonus (visual content)
    if log.snap_shot:
        score += QUALITY_IMAGE_BONUS
    
    # Link bonus (references external resources)
    if log.link:
        score += QUALITY_LINK_BONUS
    
    # Normalize to 0-1 range (max possible = 0.4 + 0.3 + 0.2 + 0.1 = 1.0)
    return min(score, 1.0)


def calculate_trending_score(log, recent_reaction_count=None, recent_comment_count=None):
    """
    Calculate trending/virality score (0.0 to 1.0).
    
    Trending = Recent engagement velocity × recency multiplier
    
    High trending score = lots of recent engagement on relatively fresh content.
    Old content with past engagement gets lower trending scores.
    
    Args:
        log: The log object
        recent_reaction_count: Reactions in last 24h (pre-computed for efficiency)
        recent_comment_count: Comments in last 24h (pre-computed for efficiency)
    
    Returns normalized trending score between 0 and 1.
    """
    # Total engagement (all-time)
    total_reactions = getattr(log, 'reaction_count', 0) or 0
    total_comments = getattr(log, 'comment_count', 0) or 0
    total_engagement = total_reactions + total_comments
    
    if total_engagement == 0:
        return 0.0
    
    # If we have recent counts, calculate velocity
    if recent_reaction_count is not None and recent_comment_count is not None:
        recent_engagement = recent_reaction_count + recent_comment_count
        # Velocity = recent / total (0 to 1)
        velocity = recent_engagement / max(total_engagement, 1)
    else:
        # Estimate based on recency
        age_hours = (now() - log.timestamp).total_seconds() / 3600
        if age_hours <= TRENDING_WINDOW_HOURS:
            velocity = 1.0  # Assume all engagement is recent for fresh logs
        else:
            # Decay: older logs have lower velocity
            velocity = max(0.1, TRENDING_WINDOW_HOURS / age_hours)
    
    # Base trending from total engagement (logarithmic to prevent domination)
    # 1 engagement = 0.1, 10 = 0.3, 100 = 0.5
    engagement_score = min(0.5, 0.1 * math.log10(total_engagement + 1))
    
    # Apply velocity multiplier
    trending_score = engagement_score * (1.0 + velocity * TRENDING_VELOCITY_WEIGHT)
    
    # Recency bonus: fresher content gets trending boost
    recency = get_recency_multiplier(log.timestamp)
    recency_factor = recency / 10.0  # Normalize to 0-1
    
    # Final trending score
    final_score = trending_score * (1.0 + recency_factor)
    
    return min(final_score, 1.0)


def calculate_personalization_score(log, user_skills, user_viewed_authors):
    """
    Calculate personalization/interest alignment score (0.0 to 1.0).
    
    Personalization signals:
    - Author's skills match user's skills (interest alignment)
    - Author is new to user (discovery bonus)
    - Content category matches user preferences
    
    Args:
        log: The log object
        user_skills: Set of user's skill IDs
        user_viewed_authors: Set of author IDs the user has seen content from
    
    Returns normalized personalization score between 0 and 1.
    """
    score = 0.0
    
    # Skill match scoring
    if user_skills and hasattr(log.user, 'skills'):
        author_skills = set(log.user.skills.values_list('id', flat=True))
        if author_skills:
            shared_skills = user_skills.intersection(author_skills)
            # More shared skills = higher relevance
            # 1 shared = 0.2, 2 = 0.35, 3+ = 0.5
            if shared_skills:
                skill_match_score = min(0.5, 0.2 + (len(shared_skills) - 1) * 0.15)
                score += skill_match_score
    
    # Discovery bonus: new authors get a boost
    if log.user_id not in user_viewed_authors:
        score += 0.3  # 30% bonus for discovering new voices
    
    # Author reputation (follower count as proxy)
    # This helps surface quality content creators
    follower_count = getattr(log.user, 'follower_count', 0)
    if follower_count:
        # Logarithmic: 10 followers = 0.1, 100 = 0.15, 1000 = 0.2
        reputation_score = min(0.2, 0.05 * math.log10(follower_count + 1))
        score += reputation_score
    
    return min(score, 1.0)


def calculate_global_recency_score(log):
    """
    Calculate recency score for Global feed (0.0 to 1.0).
    
    Uses same multipliers as Network feed but normalized to 0-1.
    """
    recency_multiplier = get_recency_multiplier(log.timestamp)
    # Normalize: max multiplier is 10.0
    return recency_multiplier / 10.0


def calculate_diversity_score(log, seen_authors, seen_skills, seen_time_buckets):
    """
    Calculate diversity bonus (0.0 to 1.0).
    
    Diversity signals:
    - New author (not seen recently in feed)
    - New skill category (introduces variety)
    - Different time bucket (temporal diversity)
    
    Args:
        log: The log object
        seen_authors: Set of author IDs already in current page
        seen_skills: Set of skill category IDs already in current page
        seen_time_buckets: Set of time bucket keys (hour) already in page
    
    Returns diversity bonus between 0 and 1.
    """
    score = 0.0
    
    # Author diversity: bonus for new authors
    if log.user_id not in seen_authors:
        score += 0.4
    
    # Skill/category diversity
    if hasattr(log.user, 'skills'):
        author_skill_ids = set(log.user.skills.values_list('id', flat=True))
        new_skills = author_skill_ids - seen_skills
        if new_skills:
            score += min(0.3, len(new_skills) * DIVERSITY_SKILL_BONUS)
    
    # Temporal diversity: spread content across time
    time_bucket = log.timestamp.strftime('%Y-%m-%d-%H')  # Hour bucket
    if time_bucket not in seen_time_buckets:
        score += DIVERSITY_TIME_SPREAD_BONUS
    
    return min(score, 1.0)


def get_global_interaction_penalty(log_id, viewed_log_ids, reacted_log_ids, commented_log_ids):
    """
    Get interaction penalty for Global feed.
    More aggressive than Network feed since we want to prioritize discovery.
    
    Returns (penalty_multiplier, interaction_type)
    """
    if log_id in commented_log_ids:
        return (GLOBAL_INTERACTION_PENALTIES['commented'], 'commented')
    elif log_id in reacted_log_ids:
        return (GLOBAL_INTERACTION_PENALTIES['reacted'], 'reacted')
    elif log_id in viewed_log_ids:
        return (GLOBAL_INTERACTION_PENALTIES['viewed'], 'viewed')
    return (1.0, None)


def calculate_global_log_score(
    log, 
    user, 
    user_skills,
    user_viewed_authors,
    viewed_log_ids, 
    reacted_log_ids, 
    commented_log_ids,
    seen_authors=None,
    seen_skills=None,
    seen_time_buckets=None,
):
    """
    Calculate Global feed score using weighted multi-factor formula.
    
    Score = Σ(weight_i × component_i) × interaction_penalty
    
    Components (normalized 0-1):
    - Quality (35%): Content richness
    - Trending (25%): Engagement velocity
    - Personalization (20%): Interest alignment
    - Recency (12%): Freshness
    - Diversity (8%): Feed variety
    
    Returns:
        float: Final weighted score
    """
    # Calculate each component (all normalized to 0-1)
    quality = calculate_quality_score(log)
    trending = calculate_trending_score(log)
    personalization = calculate_personalization_score(log, user_skills, user_viewed_authors)
    recency = calculate_global_recency_score(log)
    
    # Diversity is calculated with context (what's already in feed)
    diversity = calculate_diversity_score(
        log,
        seen_authors or set(),
        seen_skills or set(),
        seen_time_buckets or set()
    )
    
    # Weighted sum
    base_score = (
        GLOBAL_WEIGHTS['quality'] * quality +
        GLOBAL_WEIGHTS['trending'] * trending +
        GLOBAL_WEIGHTS['personalization'] * personalization +
        GLOBAL_WEIGHTS['recency'] * recency +
        GLOBAL_WEIGHTS['diversity'] * diversity
    )
    
    # Apply interaction penalty
    penalty, interaction_type = get_global_interaction_penalty(
        log.id, viewed_log_ids, reacted_log_ids, commented_log_ids
    )
    
    final_score = base_score * penalty
    
    # Store metadata for debugging/display
    log.global_scores = {
        'quality': quality,
        'trending': trending,
        'personalization': personalization,
        'recency': recency,
        'diversity': diversity,
        'penalty': penalty,
        'final': final_score,
    }
    log.user_interaction = interaction_type
    
    return final_score


def _get_global_recommendation_reason(log, user_skills):
    """
    Generate recommendation reason for Global feed logs.
    
    Based on the strongest scoring factor for this log.
    """
    scores = getattr(log, 'global_scores', {})
    
    # Find the dominant factor
    quality = scores.get('quality', 0)
    trending = scores.get('trending', 0)
    personalization = scores.get('personalization', 0)
    
    # Check shared skills
    shared_skills_count = 0
    if user_skills and hasattr(log.user, 'skills'):
        author_skills = set(log.user.skills.values_list('id', flat=True))
        shared_skills_count = len(user_skills.intersection(author_skills))
    
    # Determine best label based on scores
    if trending > 0.3:
        reaction_count = getattr(log, 'reaction_count', 0) or 0
        comment_count = getattr(log, 'comment_count', 0) or 0
        engagement = reaction_count + comment_count
        return {
            'text': 'Trending',
            'subtext': f'{engagement} engagements',
            'icon': 'fa-fire'
        }
    
    if shared_skills_count >= 2:
        return {
            'text': f'{shared_skills_count} shared skills',
            'subtext': 'Matches your interests',
            'icon': 'fa-code'
        }
    
    if quality > 0.4:
        return {
            'text': 'Quality content',
            'subtext': 'Rich technical post',
            'icon': 'fa-star'
        }
    
    if personalization > 0.3:
        return {
            'text': 'Recommended for you',
            'subtext': 'Based on your skills',
            'icon': 'fa-lightbulb-o'
        }
    
    # Default
    return {
        'text': 'Discover',
        'subtext': 'From the community',
        'icon': 'fa-globe'
    }


def get_global_feed_recency_mode(page=1, per_page=7):
    """
    INDEPENDENT Global feed algorithm for GLOBAL_FEED_USE_RECENCY_MODE.
    
    Highly optimized for performance:
    - Single SELECT query with LIMIT/OFFSET (no COUNT query)
    - Minimal field fetching via select_related()
    - Direct slicing instead of Paginator for speed
    - Lightweight page-like wrapper for template compatibility
    
    Returns all logs ordered strictly by timestamp (newest first).
    
    Args:
        page: Current page number
        per_page: Number of logs per page
    
    Returns:
        Lightweight page-like object with logs
    """
    from logs.models import Log
    
    # Calculate offset for pagination
    offset = (page - 1) * per_page
    
    # Ultra-efficient: Single query with select_related, no COUNT
    # Fetch per_page + 1 to determine if more pages exist
    logs = list(
        Log.objects
        .select_related('user__user')  # Prevents N+1 queries
        .order_by('-timestamp')        # Index-optimized ordering
        [offset:offset + per_page + 1] # Direct slicing (LIMIT/OFFSET)
    )
    
    # Check if more pages exist
    has_next = len(logs) > per_page
    has_previous = page > 1
    
    if has_next:
        logs = logs[:per_page]  # Trim to exact page size
    
    # Add minimal metadata for template compatibility (in-memory, no DB hit)
    for log in logs:
        log.feed_score = 0
        log.feed_type = 'global'
        log.is_secondary_network = False
        log.recommendation_reason = None
    
    # Create lightweight page-like object
    class SimplePage:
        def __init__(self, object_list, number, has_next, has_previous):
            self.object_list = object_list
            self.number = number
            self.has_next_page = has_next
            self.has_previous_page = has_previous
        
        def __iter__(self):
            return iter(self.object_list)
        
        def __len__(self):
            return len(self.object_list)
        
        def __getitem__(self, index):
            return self.object_list[index]
        
        def has_next(self):
            return self.has_next_page
        
        def has_previous(self):
            return self.has_previous_page
        
        def next_page_number(self):
            return self.number + 1 if self.has_next_page else None
        
        def previous_page_number(self):
            return self.number - 1 if self.has_previous_page else None
    
    return SimplePage(logs, page, has_next, has_previous)


def get_global_feed_logs(user, base_queryset, per_page, viewed_log_ids, reacted_log_ids, commented_log_ids):
    """
    Get logs for Global feed with advanced multi-factor ranking.
    
    EXCLUSIONS:
    1. Primary network (users the current user follows)
    2. Secondary network (friends-of-friends)
    3. Nearby users (<100km) - visible in Local tab
    4. User's own logs
    
    This ensures Global feed shows truly "global" content - people outside
    the user's immediate sphere of influence.
    """
    from logs.models import LogViews
    
    # Get user's skills for personalization
    user_skills = set(user.skills.values_list('id', flat=True)) if hasattr(user, 'skills') else set()
    
    # Get authors the user has viewed content from (for discovery bonus)
    user_viewed_authors = set(
        LogViews.objects.filter(user=user)
        .values_list('log__user_id', flat=True)
        .distinct()
    )
    
    # Build exclusion sets
    # 1. Primary network (direct follows)
    primary_network_ids = get_network_user_ids(user)
    
    # 2. Secondary network (friends-of-friends)
    secondary_network_ids = get_secondary_network_user_ids(user, primary_network_ids)
    
    # 3. All network users to exclude
    network_exclude_ids = primary_network_ids | secondary_network_ids | {user.id}
    
    # 4. Nearby users (<100km) - exclude if user has coordinates
    nearby_user_ids = set()
    if user.latitude and user.longitude:
        # Get all users with coordinates
        users_with_coords = userinfo.objects.filter(
            latitude__isnull=False,
            longitude__isnull=False
        ).exclude(id=user.id).values('id', 'latitude', 'longitude')
        
        for u in users_with_coords:
            distance = haversine_distance(
                user.latitude, user.longitude,
                u['latitude'], u['longitude']
            )
            if distance < GLOBAL_NEARBY_EXCLUSION_KM:
                nearby_user_ids.add(u['id'])
    
    # Combined exclusions
    all_exclude_ids = network_exclude_ids | nearby_user_ids
    
    # Fetch candidate logs (excluding network and nearby)
    candidate_logs = list(
        base_queryset
        .exclude(user_id__in=all_exclude_ids)
        .select_related('user__user')
        .prefetch_related('user__skills')
        .order_by('-timestamp')[:1000]  # Fixed limit for consistent coverage
    )
    
    # Score each log
    scored_logs = []
    
    # Track seen items for diversity scoring (progressive)
    seen_authors = set()
    seen_skills = set()
    seen_time_buckets = set()
    
    for log in candidate_logs:
        score = calculate_global_log_score(
            log=log,
            user=user,
            user_skills=user_skills,
            user_viewed_authors=user_viewed_authors,
            viewed_log_ids=viewed_log_ids,
            reacted_log_ids=reacted_log_ids,
            commented_log_ids=commented_log_ids,
            seen_authors=seen_authors,
            seen_skills=seen_skills,
            seen_time_buckets=seen_time_buckets,
        )
        
        # Add small random noise for tie-breaking (0.1% max)
        noise = random.random() * 0.001
        
        # Store metadata
        log.feed_score = score
        log.feed_type = 'global'
        log.is_secondary_network = False
        log.recommendation_reason = _get_global_recommendation_reason(log, user_skills)
        
        scored_logs.append((score, noise, log))
        
        # Update seen sets for next iteration's diversity calculation
        seen_authors.add(log.user_id)
        if hasattr(log.user, 'skills'):
            seen_skills.update(log.user.skills.values_list('id', flat=True))
        seen_time_buckets.add(log.timestamp.strftime('%Y-%m-%d-%H'))
    
    # Sort by score (descending)
    scored_logs.sort(key=lambda x: (-x[0], x[1]))
    
    # Apply author diversity limit (max 2 logs per author per page)
    author_counts = {}
    diverse_logs = []
    
    for score, noise, log in scored_logs:
        author_id = log.user_id
        current_count = author_counts.get(author_id, 0)
        
        if current_count < MAX_LOGS_PER_AUTHOR:
            diverse_logs.append(log)
            author_counts[author_id] = current_count + 1
    
    # DEBUG: Print Global feed scores
    print("\n" + "="*70)
    print(f"GLOBAL FEED SCORES FOR USER: {user.user.username}")
    print(f"Excluded: {len(primary_network_ids)} primary, {len(secondary_network_ids)} secondary, {len(nearby_user_ids)} nearby")
    print("="*70)
    for log in diverse_logs[:15]:
        scores = getattr(log, 'global_scores', {})
        print(f"  {log.sig} by @{log.user.user.username}")
        print(f"    Q:{scores.get('quality',0):.2f} T:{scores.get('trending',0):.2f} P:{scores.get('personalization',0):.2f} R:{scores.get('recency',0):.2f} D:{scores.get('diversity',0):.2f}")
        print(f"    Final: {scores.get('final',0):.3f} (penalty: {scores.get('penalty',1):.2f})")
    print("="*70 + "\n")
    
    return diverse_logs


def get_personalized_feed(request, type='network', page=1, per_page=7, cursor=None):
    """
    Personalized feed algorithm for home page.
    
    Feed types:
    - 'network': Logs sorted by timestamp (most recent first)
      * Primary network: direct follows
      * Secondary network: friends-of-friends
    - 'local': Logs ranked by proximity and relevance
    - 'global': Logs with multi-factor ranking (quality, trending, personalization)
    """
    from logs.models import Log, Reaction, Comment
    from django.conf import settings
    
    # EARLY EXIT: If global feed + recency mode enabled, use independent algorithm
    if type == 'global' and getattr(settings, 'GLOBAL_FEED_USE_RECENCY_MODE', False):
        return get_global_feed_recency_mode(page=page, per_page=per_page)
    
    user = request.user.info
    
    # Get primary network (users I follow)
    primary_network_ids = get_network_user_ids(user)
    
    if type == 'network':
        # NETWORK FEED: Pure recency-based sorting (optimized for performance)
        # Fetches logs from both primary and secondary connections sorted by timestamp
        
        # Get secondary network IDs
        secondary_network_ids = get_secondary_network_user_ids(user, primary_network_ids)
        
        # Combine both primary and secondary network IDs
        all_network_ids = primary_network_ids | secondary_network_ids
        
        # Optimized: Fetch logs sorted by timestamp with minimal fields loaded
        # Database handles sorting using index on timestamp column
        # Pagination happens at database level (not in Python)
        logs_list = list(
            Log.objects.filter(user_id__in=all_network_ids)
            .select_related('user__user')  # Prevent N+1 queries
            .annotate(
                reaction_count=Count('reactions', distinct=True),
                comment_count=Count('comments', distinct=True),
            )
            .order_by('-timestamp')  # Database-level sort using index
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
        # Get user interaction history for freshness calculation (used by Global feed)
        viewed_log_ids, reacted_log_ids, commented_log_ids = get_user_interaction_sets(user)
        
        # Base queryset with annotations for engagement metrics
        base_queryset = Log.objects.select_related('user__user').annotate(
            reaction_count=Count('reactions', distinct=True),
            comment_count=Count('comments', distinct=True),
        )
        
        # GLOBAL FEED: Sophisticated multi-factor ranking
        # Excludes: primary network, secondary network, nearby users (<100km)
        # Weights: quality(35%), trending(25%), personalization(20%), recency(12%), diversity(8%)
        logs_list = get_global_feed_logs(
            user, base_queryset, per_page,
            viewed_log_ids, reacted_log_ids, commented_log_ids
        )
        
    else:
        # Get user interaction history for freshness calculation (used by Local feed)
        viewed_log_ids, reacted_log_ids, commented_log_ids = get_user_interaction_sets(user)
        
        # Base queryset with annotations for engagement metrics
        base_queryset = Log.objects.select_related('user__user').annotate(
            reaction_count=Count('reactions', distinct=True),
            comment_count=Count('comments', distinct=True),
        )
        
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