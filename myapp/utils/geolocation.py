"""
Browser-Only Geolocation System
================================

Simple location resolution for Local Feed using ONLY Browser Geolocation.
No IP fallback. No third-party APIs.

Rules:
- Browser Geolocation is the ONLY source
- 24 hour freshness window
- If denied: show message, no fallback
"""

import logging
from datetime import timedelta
from decimal import Decimal
from django.utils import timezone

logger = logging.getLogger(__name__)

# Freshness interval - 24 hours
LOCATION_FRESHNESS_HOURS = 24


def is_location_fresh(user_info):
    """
    Check if stored location is fresh (< 24 hours old).
    
    Returns:
        bool: True if location is fresh and usable
    """
    if not user_info.browser_latitude or not user_info.browser_longitude:
        return False
    
    if not user_info.browser_location_updated_at:
        return False
    
    age = timezone.now() - user_info.browser_location_updated_at
    return age < timedelta(hours=LOCATION_FRESHNESS_HOURS)


def is_location_stale(user_info):
    """
    Check if stored location exists but is stale (>= 24 hours old).
    
    Returns:
        bool: True if location needs refresh
    """
    if not user_info.browser_latitude or not user_info.browser_longitude:
        return False
    
    if not user_info.browser_location_updated_at:
        return False
    
    age = timezone.now() - user_info.browser_location_updated_at
    return age >= timedelta(hours=LOCATION_FRESHNESS_HOURS)


def update_location(user_info, latitude, longitude):
    """
    Update user's location from browser geolocation.
    
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
        
        # Also update legacy fields
        user_info.latitude = Decimal(str(latitude))
        user_info.longitude = Decimal(str(longitude))
        
        user_info.save(update_fields=[
            'browser_latitude',
            'browser_longitude',
            'browser_location_updated_at',
            'browser_permission_status',
            'latitude',
            'longitude'
        ])
        
        logger.info(f"Updated location for user {user_info.user.username}: ({latitude}, {longitude})")
        return True
        
    except Exception as e:
        logger.error(f"Failed to update location: {e}")
        return False


def set_permission_denied(user_info):
    """
    Record that user denied browser geolocation permission.
    
    Args:
        user_info: userinfo model instance
    """
    try:
        user_info.browser_permission_status = 'denied'
        user_info.save(update_fields=['browser_permission_status'])
        logger.info(f"Recorded permission denial for user {user_info.user.username}")
    except Exception as e:
        logger.error(f"Failed to record permission denial: {e}")


def get_geolocation_status(user_info):
    """
    Get geolocation status for frontend decision-making.
    
    Returns:
        dict with status and recommended action
        
    Actions:
        - 'use_location': Fresh location exists, use it
        - 'request_location': Need to request browser location
        - 'retry_request_location': Previously denied, but should retry (user may have changed permission)
    """
    has_location = bool(user_info.browser_latitude and user_info.browser_longitude)
    location_fresh = is_location_fresh(user_info)
    location_stale = is_location_stale(user_info)
    permission_status = user_info.browser_permission_status
    
    status = {
        'has_location': has_location,
        'is_fresh': location_fresh,
        'is_stale': location_stale,
        'permission_status': permission_status,
        'latitude': float(user_info.browser_latitude) if user_info.browser_latitude else None,
        'longitude': float(user_info.browser_longitude) if user_info.browser_longitude else None,
        'updated_at': user_info.browser_location_updated_at.isoformat() if user_info.browser_location_updated_at else None,
    }
    
    # Determine recommended action
    # Priority 1: If location is fresh (< 24h), use it
    if location_fresh:
        status['recommended_action'] = 'use_location'
    
    # Priority 2: If permission was denied, still try again (user may have changed browser permission)
    # Frontend will handle showing message if still denied
    elif permission_status == 'denied':
        status['recommended_action'] = 'retry_request_location'
    
    # Priority 3: Request location if stale, missing, or no timestamp
    else:
        status['recommended_action'] = 'request_location'
    
    return status


