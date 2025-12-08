"""
MVP Geolocation System
======================

Clean, simple location resolution for Local Feed:
1. Browser GPS (48h freshness) - Primary
2. IP geolocation (12h freshness) - Fallback
3. Global Feed - Final fallback

All IP API calls happen client-side to use user's quota, not server's.
"""

import logging
from datetime import timedelta
from decimal import Decimal
from django.utils import timezone

logger = logging.getLogger(__name__)

# Freshness intervals per MVP spec
BROWSER_FRESHNESS_HOURS = 48
IP_FRESHNESS_HOURS = 12


def is_browser_location_fresh(user_info):
    """
    Check if browser location is fresh (< 48 hours old).
    
    Returns:
        bool: True if browser location is fresh and usable
    """
    if not user_info.browser_latitude or not user_info.browser_longitude:
        return False
    
    if not user_info.browser_location_updated_at:
        return False
    
    age = timezone.now() - user_info.browser_location_updated_at
    return age < timedelta(hours=BROWSER_FRESHNESS_HOURS)


def is_browser_location_stale(user_info):
    """
    Check if browser location exists but is stale (>= 48 hours old).
    
    Returns:
        bool: True if browser location exists but needs refresh
    """
    if not user_info.browser_latitude or not user_info.browser_longitude:
        return False
    
    if not user_info.browser_location_updated_at:
        return False
    
    age = timezone.now() - user_info.browser_location_updated_at
    return age >= timedelta(hours=BROWSER_FRESHNESS_HOURS)


def is_ip_location_fresh(user_info):
    """
    Check if IP location is fresh (< 12 hours old).
    
    Returns:
        bool: True if IP location is fresh and usable
    """
    if not user_info.ip_latitude or not user_info.ip_longitude:
        return False
    
    if not user_info.ip_location_updated_at:
        return False
    
    age = timezone.now() - user_info.ip_location_updated_at
    return age < timedelta(hours=IP_FRESHNESS_HOURS)


def is_ip_location_stale(user_info):
    """
    Check if IP location needs refresh (>= 12 hours old or missing).
    
    Returns:
        bool: True if IP location should be refreshed
    """
    if not user_info.ip_latitude or not user_info.ip_longitude:
        return True
    
    if not user_info.ip_location_updated_at:
        return True
    
    age = timezone.now() - user_info.ip_location_updated_at
    return age >= timedelta(hours=IP_FRESHNESS_HOURS)


def update_browser_location(user_info, latitude, longitude):
    """
    Update user's browser GPS location.
    Called when user grants permission and browser returns coordinates.
    
    Args:
        user_info: userinfo model instance
        latitude: float/Decimal latitude
        longitude: float/Decimal longitude
    
    Returns:
        bool: True if update succeeded
    """
    try:
        user_info.browser_latitude = Decimal(str(latitude))
        user_info.browser_longitude = Decimal(str(longitude))
        user_info.browser_location_updated_at = timezone.now()
        user_info.browser_permission_status = 'allowed'
        
        user_info.save(update_fields=[
            'browser_latitude',
            'browser_longitude',
            'browser_location_updated_at',
            'browser_permission_status',
            'latitude',  # Legacy field auto-updated by save()
            'longitude'
        ])
        
        logger.info(f"Updated browser location for user {user_info.user.username}: "
                   f"({latitude}, {longitude})")
        return True
        
    except Exception as e:
        logger.error(f"Failed to update browser location: {e}")
        return False


def update_ip_location(user_info, latitude, longitude):
    """
    Update user's IP-based location.
    Called from client-side after IP API returns coordinates.
    
    Args:
        user_info: userinfo model instance
        latitude: float/Decimal latitude
        longitude: float/Decimal longitude
    
    Returns:
        bool: True if update succeeded
    """
    try:
        user_info.ip_latitude = Decimal(str(latitude))
        user_info.ip_longitude = Decimal(str(longitude))
        user_info.ip_location_updated_at = timezone.now()
        
        user_info.save(update_fields=[
            'ip_latitude',
            'ip_longitude',
            'ip_location_updated_at',
            'latitude',  # Legacy field auto-updated by save()
            'longitude'
        ])
        
        logger.info(f"Updated IP location for user {user_info.user.username}: "
                   f"({latitude}, {longitude})")
        return True
        
    except Exception as e:
        logger.error(f"Failed to update IP location: {e}")
        return False


def set_browser_permission_denied(user_info):
    """
    Record that user denied browser geolocation permission.
    System will not prompt again and will use IP fallback.
    
    Args:
        user_info: userinfo model instance
    """
    try:
        user_info.browser_permission_status = 'denied'
        user_info.save(update_fields=['browser_permission_status'])
        logger.info(f"Recorded browser permission denial for user {user_info.user.username}")
    except Exception as e:
        logger.error(f"Failed to record permission denial: {e}")


def get_geolocation_status(user_info):
    """
    Get complete geolocation status for decision-making.
    Used by frontend to determine which action to take.
    
    Returns:
        dict with:
            - has_browser_location: bool
            - browser_is_fresh: bool
            - browser_is_stale: bool
            - has_ip_location: bool
            - ip_is_fresh: bool
            - ip_needs_refresh: bool
            - browser_permission_status: str ('unknown'/'allowed'/'denied')
            - recommended_action: str (what frontend should do)
    """
    status = {
        'has_browser_location': bool(user_info.browser_latitude and user_info.browser_longitude),
        'browser_is_fresh': is_browser_location_fresh(user_info),
        'browser_is_stale': is_browser_location_stale(user_info),
        'has_ip_location': bool(user_info.ip_latitude and user_info.ip_longitude),
        'ip_is_fresh': is_ip_location_fresh(user_info),
        'ip_needs_refresh': is_ip_location_stale(user_info),
        'browser_permission_status': user_info.browser_permission_status,
        'browser_latitude': float(user_info.browser_latitude) if user_info.browser_latitude else None,
        'browser_longitude': float(user_info.browser_longitude) if user_info.browser_longitude else None,
        'ip_latitude': float(user_info.ip_latitude) if user_info.ip_latitude else None,
        'ip_longitude': float(user_info.ip_longitude) if user_info.ip_longitude else None,
        'browser_updated_at': user_info.browser_location_updated_at.isoformat() if user_info.browser_location_updated_at else None,
        'ip_updated_at': user_info.ip_location_updated_at.isoformat() if user_info.ip_location_updated_at else None,
    }
    
    # Determine recommended action based on MVP algorithm
    if status['browser_is_fresh']:
        status['recommended_action'] = 'use_browser_location'
    elif status['browser_is_stale'] and status['browser_permission_status'] == 'allowed':
        status['recommended_action'] = 'refresh_browser_location'
    elif status['browser_permission_status'] == 'denied' and status['ip_is_fresh']:
        status['recommended_action'] = 'use_ip_location'
    elif status['browser_permission_status'] == 'denied' and status['ip_needs_refresh']:
        status['recommended_action'] = 'refresh_ip_location'
    elif not status['has_browser_location'] and not status['has_ip_location']:
        status['recommended_action'] = 'request_browser_permission'
    elif status['ip_is_fresh']:
        status['recommended_action'] = 'use_ip_location'
    elif status['ip_needs_refresh']:
        status['recommended_action'] = 'refresh_ip_location'
    else:
        status['recommended_action'] = 'show_global_feed'
    
    return status
