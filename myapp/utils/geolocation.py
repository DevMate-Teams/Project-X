"""
Geolocation utilities for auto-detecting user location.

Supports:
1. IP-based geolocation (server-side, automatic)
2. Browser Geolocation API (client-side, more accurate)
3. Periodic refresh to handle users who move locations

IMPORTANT: Two separate timestamps track each method independently:
- location_ip_updated_at: Tracks IP-based updates (every 24 hours)
- location_browser_updated_at: Tracks browser GPS updates (every 7 days)

This separation ensures:
- IP fallback works even if browser location is fresh
- Browser prompt appears even if IP location is fresh
- Each method refreshes on its own schedule
"""

import requests
import logging
from decimal import Decimal
from datetime import timedelta
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

# Location refresh configuration
IP_LOCATION_REFRESH_HOURS = 24  # Refresh IP-based location every 24 hours
BROWSER_LOCATION_REFRESH_HOURS = 168  # Refresh browser location every 7 days (more accurate, less frequent)


# Free IP geolocation services (in order of preference)
IP_GEOLOCATION_SERVICES = [
    {
        'name': 'ip-api.com',
        'url': 'http://ip-api.com/json/{ip}',
        'lat_key': 'lat',
        'lon_key': 'lon',
        'city_key': 'city',
        'state_key': 'regionName',
        'country_key': 'country',
        'success_key': 'status',
        'success_value': 'success',
    },
    {
        'name': 'ipwho.is',
        'url': 'https://ipwho.is/{ip}',
        'lat_key': 'latitude',
        'lon_key': 'longitude',
        'city_key': 'city',
        'state_key': 'region',
        'country_key': 'country',
        'success_key': 'success',
        'success_value': True,
    },
]


def get_client_ip(request):
    """
    Extract the client's IP address from the request.
    Handles reverse proxies (X-Forwarded-For header).
    """
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        # Take the first IP in the chain (original client)
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR')
    
    # Don't use localhost/private IPs
    if ip in ('127.0.0.1', 'localhost', '::1'):
        return None
    if ip and ip.startswith(('10.', '172.', '192.168.')):
        return None
    
    return ip


def get_location_from_ip(ip_address):
    """
    Get geolocation data from IP address using free API services.
    
    Returns dict with:
        - latitude (Decimal)
        - longitude (Decimal)
        - city (str)
        - state (str)
        - country (str)
    
    Returns None if geolocation fails.
    """
    if not ip_address:
        return None
    
    for service in IP_GEOLOCATION_SERVICES:
        try:
            url = service['url'].format(ip=ip_address)
            response = requests.get(url, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                
                # Check if request was successful
                success_key = service.get('success_key')
                if success_key:
                    if data.get(success_key) != service.get('success_value'):
                        continue
                
                lat = data.get(service['lat_key'])
                lon = data.get(service['lon_key'])
                
                if lat is not None and lon is not None:
                    return {
                        'latitude': Decimal(str(lat)),
                        'longitude': Decimal(str(lon)),
                        'city': data.get(service['city_key'], ''),
                        'state': data.get(service['state_key'], ''),
                        'country': data.get(service['country_key'], ''),
                    }
                    
        except (requests.RequestException, ValueError, KeyError) as e:
            logger.warning(f"Geolocation service {service['name']} failed: {e}")
            continue
    
    return None


def is_ip_location_stale(user_info):
    """
    Check if IP-based location is stale and needs refresh.
    Uses location_ip_updated_at timestamp.
    
    Returns:
        bool: True if IP location needs refresh, False otherwise
    """
    # No location set - definitely needs update
    if not user_info.latitude or not user_info.longitude:
        return True
    
    # No IP timestamp - treat as stale
    if not user_info.location_ip_updated_at:
        return True
    
    # Check if IP location is older than 24 hours
    stale_threshold = timezone.now() - timedelta(hours=IP_LOCATION_REFRESH_HOURS)
    return user_info.location_ip_updated_at < stale_threshold


def is_browser_location_stale(user_info):
    """
    Check if browser-based location is stale and needs refresh.
    Uses location_browser_updated_at timestamp.
    
    Returns:
        bool: True if browser location needs refresh, False otherwise
    """
    # No location set - definitely needs browser prompt
    if not user_info.latitude or not user_info.longitude:
        return True
    
    # No browser timestamp - user never granted permission, prompt them
    if not user_info.location_browser_updated_at:
        return True
    
    # Check if browser location is older than 7 days
    stale_threshold = timezone.now() - timedelta(hours=BROWSER_LOCATION_REFRESH_HOURS)
    return user_info.location_browser_updated_at < stale_threshold


def update_user_location_from_ip(user_info, request, force=False):
    """
    Auto-update user's latitude/longitude from their IP address.
    Updates if IP location is stale or not set.
    
    Args:
        user_info: The userinfo model instance
        request: The Django request object
        force: If True, update regardless of staleness
    
    Returns:
        bool: True if location was updated, False otherwise
    """
    # Check if update is needed (unless forced)
    if not force and not is_ip_location_stale(user_info):
        return False
    
    ip_address = get_client_ip(request)
    if not ip_address:
        return False
    
    location_data = get_location_from_ip(ip_address)
    if not location_data:
        return False
    
    try:
        user_info.latitude = location_data['latitude']
        user_info.longitude = location_data['longitude']
        user_info.location_ip_updated_at = timezone.now()  # Update IP timestamp only
        
        # Also update city/state/country
        if location_data['city']:
            user_info.city = location_data['city']
        if location_data['state']:
            user_info.state = location_data['state']
        if location_data['country']:
            user_info.country = location_data['country']
        
        user_info.save(update_fields=[
            'latitude', 'longitude', 'location_ip_updated_at', 'city', 'state', 'country'
        ])
        
        logger.info(f"Updated IP location for user {user_info.user.username}: "
                   f"({location_data['latitude']}, {location_data['longitude']})")
        return True
        
    except Exception as e:
        logger.error(f"Failed to update user location from IP: {e}")
        return False


def update_user_location_from_browser(user_info, latitude, longitude):
    """
    Update user's location from browser Geolocation API.
    This is more accurate than IP-based geolocation.
    Always updates when called (browser location is user-initiated).
    
    Args:
        user_info: The userinfo model instance
        latitude: Browser-provided latitude
        longitude: Browser-provided longitude
    
    Returns:
        bool: True if location was updated, False otherwise
    """
    try:
        user_info.latitude = Decimal(str(latitude))
        user_info.longitude = Decimal(str(longitude))
        user_info.location_browser_updated_at = timezone.now()  # Update browser timestamp only
        user_info.save(update_fields=['latitude', 'longitude', 'location_browser_updated_at'])
        
        logger.info(f"Updated browser location for user {user_info.user.username}: "
                   f"({latitude}, {longitude})")
        return True
        
    except Exception as e:
        logger.error(f"Failed to update browser location: {e}")
        return False


def should_request_browser_location(user_info):
    """
    Check if we should request browser geolocation from the user.
    Uses the browser-specific timestamp.
    
    Browser location is more accurate but requires user permission,
    so we request it less frequently than IP-based updates.
    """
    return is_browser_location_stale(user_info)
