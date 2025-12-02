"""
Geolocation utilities for auto-detecting user location.

Supports:
1. IP-based geolocation (server-side, automatic)
2. Browser Geolocation API (client-side, more accurate)
"""

import requests
import logging
from decimal import Decimal
from django.conf import settings

logger = logging.getLogger(__name__)


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


def update_user_location_from_ip(user_info, request):
    """
    Auto-update user's latitude/longitude from their IP address.
    Only updates if user doesn't already have coordinates set.
    
    Args:
        user_info: The userinfo model instance
        request: The Django request object
    
    Returns:
        bool: True if location was updated, False otherwise
    """
    # Skip if user already has coordinates
    if user_info.latitude and user_info.longitude:
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
        
        # Also update city/state/country if not set
        if not user_info.city and location_data['city']:
            user_info.city = location_data['city']
        if not user_info.state and location_data['state']:
            user_info.state = location_data['state']
        if not user_info.country and location_data['country']:
            user_info.country = location_data['country']
        
        user_info.save(update_fields=[
            'latitude', 'longitude', 'city', 'state', 'country'
        ])
        
        logger.info(f"Updated location for user {user_info.user.username}: "
                   f"({location_data['latitude']}, {location_data['longitude']})")
        return True
        
    except Exception as e:
        logger.error(f"Failed to update user location: {e}")
        return False


def update_user_location_from_browser(user_info, latitude, longitude):
    """
    Update user's location from browser Geolocation API.
    This is more accurate than IP-based geolocation.
    
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
        user_info.save(update_fields=['latitude', 'longitude'])
        
        logger.info(f"Updated browser location for user {user_info.user.username}: "
                   f"({latitude}, {longitude})")
        return True
        
    except Exception as e:
        logger.error(f"Failed to update browser location: {e}")
        return False
