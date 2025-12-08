/**
 * Feed Infinite Scroll & View Tracking
 * 
 * Implements:
 * - Infinite scroll pagination for home feed
 * - Log view tracking for feed freshness calculation
 * - Intersection Observer for detecting visible logs
 */

(function() {
    'use strict';

    // ==========================================================================
    // Configuration
    // ==========================================================================
    const CONFIG = {
        // Scroll trigger threshold (how far from bottom to trigger load)
        scrollThreshold: 300,
        // Debounce delay for scroll events (ms)
        scrollDebounce: 100,
        // Intersection threshold for view tracking (% visible)
        viewThreshold: 0.5,
        // Minimum time visible to count as viewed (ms)
        viewMinTime: 1000,
        // Batch size for view tracking requests
        viewBatchSize: 5,
        // Batch delay before sending view tracking request (ms)
        viewBatchDelay: 2000,
    };

    // ==========================================================================
    // State
    // ==========================================================================
    let nextCursor = null;
    let isLoading = false;
    let hasMoreContent = true;
    let currentFeedType = 'network';
    
    // View tracking state
    let viewedLogs = new Set();
    let pendingViews = [];
    let viewBatchTimer = null;

    // ==========================================================================
    // Utility Functions
    // ==========================================================================
    function getCSRFToken() {
        let cookieValue = null;
        if (document.cookie && document.cookie !== "") {
            const cookies = document.cookie.split(";");
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.startsWith("csrftoken=")) {
                    cookieValue = cookie.substring("csrftoken=".length);
                    break;
                }
            }
        }
        return cookieValue;
    }

    function debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    }

    function getFeedTypeFromURL() {
        const urlParams = new URLSearchParams(window.location.search);
        return urlParams.get('feed') || 'network';
    }

    // ==========================================================================
    // Infinite Scroll Implementation
    // ==========================================================================
    function initInfiniteScroll() {
        const feedContainer = document.getElementById('feed-container');
        const loadingIndicator = document.getElementById('loading');

        if (!feedContainer) {
            console.log('Feed container not found, skipping infinite scroll init');
            return;
        }

        currentFeedType = getFeedTypeFromURL();
        
        // Initialize cursor from data attribute (set by server on initial load)
        const initialCursor = feedContainer.dataset.nextCursor;
        if (initialCursor && initialCursor !== 'None') {
            nextCursor = initialCursor;
        }
        
        // Check if there's more content from server
        const hasNext = feedContainer.dataset.hasNext;
        if (hasNext !== undefined) {
            hasMoreContent = hasNext === 'True' || hasNext === 'true';
        }

        // Create loading indicator if it doesn't exist
        if (!loadingIndicator) {
            const loading = document.createElement('div');
            loading.id = 'loading';
            loading.className = 'text-center my-4 hidden';
            loading.innerHTML = `
                <div class="flex items-center justify-center gap-2">
                    <div class="w-4 h-4 border-2 border-green-500 border-t-transparent rounded-full animate-spin"></div>
                    <span class="text-gray-500">Loading more...</span>
                </div>
            `;
            feedContainer.parentNode.insertBefore(loading, feedContainer.nextSibling);
        }

        // Set up scroll listener
        const handleScroll = debounce(() => {
            if (isLoading || !hasMoreContent) return;

            const scrollPosition = window.innerHeight + window.scrollY;
            const documentHeight = document.documentElement.scrollHeight;

            if (documentHeight - scrollPosition < CONFIG.scrollThreshold) {
                loadMoreContent();
            }
        }, CONFIG.scrollDebounce);

        window.addEventListener('scroll', handleScroll);
    }

    function loadMoreContent() {
        if (isLoading || !hasMoreContent || !nextCursor) return;

        isLoading = true;
        const loadingIndicator = document.getElementById('loading');
        const feedContainer = document.getElementById('feed-container');

        if (loadingIndicator) {
            loadingIndicator.classList.remove('hidden');
        }

        // Use cursor-based pagination
        const url = `/load-more-feed/?cursor=${encodeURIComponent(nextCursor)}&feed=${currentFeedType}`;

        fetch(url, {
            method: 'GET',
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.html && data.html.trim() !== '') {
                // Create a temporary container to parse the HTML
                const tempDiv = document.createElement('div');
                tempDiv.innerHTML = data.html;

                // Append each child to the feed container
                while (tempDiv.firstChild) {
                    feedContainer.appendChild(tempDiv.firstChild);
                }

                // Re-initialize view tracking for new items
                initViewTracking();
                
                // Re-initialize syntax highlighting for new items
                if (typeof hljs !== 'undefined') {
                    feedContainer.querySelectorAll('pre code:not(.hljs)').forEach((block) => {
                        hljs.highlightElement(block);
                    });
                }
            }

            // Update cursor and hasMoreContent from response
            hasMoreContent = data.has_next;
            nextCursor = data.next_cursor;

            if (!hasMoreContent && loadingIndicator) {
                loadingIndicator.innerHTML = `
                     <div class="flex flex-col items-center gap-2 py-4">
                        <i class="fa-solid fa-check-circle text-2xl text-green-500"></i>
                        <p class="text-sm text-[#7d8590] font-medium">All caught up!</p>
                    </div>
                `;
                loadingIndicator.classList.remove('hidden');
            }
        })
        .catch(error => {
            console.error('Error loading more content:', error);
            // Don't revert cursor on error - keep trying from same position
        })
        .finally(() => {
            isLoading = false;
            if (hasMoreContent && loadingIndicator) {
                loadingIndicator.classList.add('hidden');
            }
        });
    }

    // ==========================================================================
    // View Tracking Implementation
    // ==========================================================================
    function initViewTracking() {
        const feedContainer = document.getElementById('feed-container');
        if (!feedContainer) return;

        // Get all log cards that haven't been tracked yet
        const logCards = feedContainer.querySelectorAll('[data-log-sig]:not([data-view-tracked])');

        // Create intersection observer for view tracking
        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    const logSig = entry.target.dataset.logSig;
                    
                    if (logSig && !viewedLogs.has(logSig)) {
                        // Start timer for minimum view time
                        entry.target.viewTimer = setTimeout(() => {
                            trackLogView(logSig);
                            entry.target.dataset.viewTracked = 'true';
                            observer.unobserve(entry.target);
                        }, CONFIG.viewMinTime);
                    }
                } else {
                    // Cancel timer if log scrolls out of view before min time
                    if (entry.target.viewTimer) {
                        clearTimeout(entry.target.viewTimer);
                        entry.target.viewTimer = null;
                    }
                }
            });
        }, {
            threshold: CONFIG.viewThreshold
        });

        // Observe all log cards
        logCards.forEach(card => {
            observer.observe(card);
        });
    }

    function trackLogView(logSig) {
        if (viewedLogs.has(logSig)) return;

        viewedLogs.add(logSig);
        pendingViews.push(logSig);

        // Debounce batch sending
        if (viewBatchTimer) {
            clearTimeout(viewBatchTimer);
        }

        // Send batch if we've hit the batch size
        if (pendingViews.length >= CONFIG.viewBatchSize) {
            sendViewBatch();
        } else {
            // Otherwise schedule batch send
            viewBatchTimer = setTimeout(sendViewBatch, CONFIG.viewBatchDelay);
        }
    }

    function sendViewBatch() {
        if (pendingViews.length === 0) return;

        const logSigs = [...pendingViews];
        pendingViews = [];

        fetch('/logs/api/track-views/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCSRFToken(),
            },
            body: JSON.stringify({ log_sigs: logSigs })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                console.log(`Tracked ${data.total} log views`);
            }
        })
        .catch(error => {
            console.error('Error tracking views:', error);
            // Re-add failed sigs back to pending for retry
            logSigs.forEach(sig => {
                if (!pendingViews.includes(sig)) {
                    pendingViews.push(sig);
                }
            });
        });
    }

    // Send any remaining pending views before page unload
    function flushPendingViews() {
        if (pendingViews.length === 0) return;

        // Use sendBeacon for reliability on page unload
        const data = JSON.stringify({ log_sigs: pendingViews });
        navigator.sendBeacon('/logs/api/track-views/', new Blob([data], { type: 'application/json' }));
        pendingViews = [];
    }

    // ==========================================================================
    // Initialization
    // ==========================================================================
    function init() {
        // Initialize geolocation on any page (not just feed pages)
        // This ensures new users get prompted regardless of which tab they visit first
        initGeolocation();
        
        // Only initialize feed-specific features on pages with feed container
        if (!document.getElementById('feed-container')) {
            console.log('No feed container found, skipping feed scroll init');
            return;
        }

        initInfiniteScroll();
        initViewTracking();

        // Flush pending views on page unload
        window.addEventListener('beforeunload', flushPendingViews);
        window.addEventListener('pagehide', flushPendingViews);

        console.log('Feed scroll & view tracking initialized');
    }

    // ==========================================================================
    // MVP Geolocation System for Local Feed
    // ==========================================================================
    //
    // PRIORITY ORDER (Never Change):
    // 1. Fresh Browser Location (< 48 hours)
    // 2. Fresh IP Location (< 12 hours)
    // 3. Forced IP Refresh
    // 4. Global Feed Fallback
    //
    // All IP API calls happen client-side (user's quota, not server's).
    // ==========================================================================

    // LocalStorage key to prevent reload loops
    const GEO_JUST_UPDATED_KEY = 'geo_just_updated';
    const GEO_UPDATE_COOLDOWN_MS = 5000; // 5 seconds cooldown after update

    // IP Geolocation API services (client-side, user's quota)
    const IP_GEOLOCATION_APIS = [
        {
            name: 'ip-api.com',
            url: 'http://ip-api.com/json/',
            parse: (data) => data.status === 'success' ? { lat: data.lat, lon: data.lon } : null
        },
        {
            name: 'ipwho.is',
            url: 'https://ipwho.is/',
            parse: (data) => data.success === true ? { lat: data.latitude, lon: data.longitude } : null
        }
    ];

    /**
     * Initialize geolocation for Local feed.
     * Only runs on Local tab, implements MVP algorithm.
     */
    function initGeolocation() {
        // Only run on Local feed
        if (getFeedTypeFromURL() !== 'local') {
            return;
        }

        // CRITICAL: Prevent reload loop after location update
        const justUpdated = localStorage.getItem(GEO_JUST_UPDATED_KEY);
        if (justUpdated) {
            const timeSinceUpdate = Date.now() - parseInt(justUpdated);
            if (timeSinceUpdate < GEO_UPDATE_COOLDOWN_MS) {
                console.log('[Geo MVP] Just updated location, skipping check to prevent loop');
                localStorage.removeItem(GEO_JUST_UPDATED_KEY);
                return;
            }
            // Expired, remove it
            localStorage.removeItem(GEO_JUST_UPDATED_KEY);
        }

        console.log('[Geo MVP] Initializing geolocation for Local feed...');

        // Fetch server status
        fetch('/api/geolocation/status/', {
            method: 'GET',
            headers: { 'X-Requested-With': 'XMLHttpRequest' },
            credentials: 'same-origin'
        })
        .then(response => response.ok ? response.json() : Promise.reject('Status fetch failed'))
        .then(status => {
            console.log('[Geo MVP] Status:', status);
            executeMVPAlgorithm(status);
        })
        .catch(error => {
            console.error('[Geo MVP] Status check failed:', error);
            // Graceful degradation: Local feed still works without location
        });
    }

    /**
     * Execute MVP algorithm based on server status.
     * Follows LOCATION_COORDINATES.MD spec exactly.
     */
    function executeMVPAlgorithm(status) {
        const action = status.recommended_action;
        
        console.log('[Geo MVP] Recommended action:', action);

        switch (action) {
            case 'use_browser_location':
                // Browser location is fresh (< 48h), use it
                console.log('[Geo MVP] Using fresh browser location');
                break;

            case 'refresh_browser_location':
                // Browser location is stale but permission was granted, try silent refresh
                console.log('[Geo MVP] Refreshing stale browser location');
                attemptBrowserRefresh();
                break;

            case 'request_browser_permission':
                // First-time user, no location at all
                console.log('[Geo MVP] First-time user, requesting browser permission');
                requestBrowserPermission();
                break;

            case 'use_ip_location':
                // IP location is fresh (< 12h), use it
                console.log('[Geo MVP] Using fresh IP location');
                break;

            case 'refresh_ip_location':
                // IP location is stale or missing, refresh it (client-side)
                console.log('[Geo MVP] Refreshing IP location (client-side)');
                fetchIPLocation();
                break;

            case 'show_global_feed':
                // Both sources failed, redirect to Global
                console.log('[Geo MVP] No location available, suggesting Global feed');
                showGlobalFeedMessage();
                break;

            default:
                console.warn('[Geo MVP] Unknown action:', action);
        }
    }

    /**
     * Request browser geolocation permission (first-time user).
     */
    function requestBrowserPermission() {
        if (!navigator.geolocation) {
            console.log('[Geo MVP] Browser API unavailable, falling back to IP');
            fetchIPLocation();
            return;
        }

        navigator.geolocation.getCurrentPosition(
            // SUCCESS
            (position) => {
                const { latitude, longitude } = position.coords;
                console.log('[Geo MVP] Browser permission granted:', latitude.toFixed(4), longitude.toFixed(4));
                saveBrowserLocation(latitude, longitude);
            },
            // ERROR
            (error) => {
                console.log('[Geo MVP] Browser permission denied/failed:', error.message);
                
                // Record denial on server
                if (error.code === error.PERMISSION_DENIED) {
                    recordPermissionDenied();
                }
                
                // Fallback to IP
                fetchIPLocation();
            },
            {
                enableHighAccuracy: true,
                timeout: 10000,
                maximumAge: 300000
            }
        );
    }

    /**
     * Attempt silent browser location refresh (permission already granted).
     */
    function attemptBrowserRefresh() {
        if (!navigator.geolocation) {
            console.log('[Geo MVP] Browser API unavailable during refresh');
            fetchIPLocation();
            return;
        }

        navigator.geolocation.getCurrentPosition(
            // SUCCESS
            (position) => {
                const { latitude, longitude } = position.coords;
                console.log('[Geo MVP] Browser refresh successful');
                saveBrowserLocation(latitude, longitude);
            },
            // ERROR
            (error) => {
                console.log('[Geo MVP] Browser refresh failed:', error.message);
                fetchIPLocation();
            },
            {
                enableHighAccuracy: true,
                timeout: 10000,
                maximumAge: 300000
            }
        );
    }

    /**
     * Save browser GPS coordinates to server.
     */
    function saveBrowserLocation(latitude, longitude) {
        fetch('/api/geolocation/browser/update/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCSRFToken(),
                'X-Requested-With': 'XMLHttpRequest',
            },
            credentials: 'same-origin',
            body: JSON.stringify({ latitude, longitude })
        })
        .then(response => response.ok ? response.json() : Promise.reject('Browser update failed'))
        .then(data => {
            if (data.success) {
                console.log('[Geo MVP] Browser location saved, reloading...');
                // Set flag before reload to prevent infinite loop
                localStorage.setItem(GEO_JUST_UPDATED_KEY, Date.now().toString());
                window.location.reload();
            }
        })
        .catch(error => {
            console.error('[Geo MVP] Failed to save browser location:', error);
            fetchIPLocation();  // Fallback to IP
        });
    }

    /**
     * Fetch IP-based location from client-side API (user's quota).
     * Tries multiple APIs in sequence until one succeeds.
     */
    function fetchIPLocation() {
        console.log('[Geo MVP] Fetching IP location from client-side APIs...');

        // Try each API in sequence
        tryIPAPI(0);

        function tryIPAPI(index) {
            if (index >= IP_GEOLOCATION_APIS.length) {
                console.warn('[Geo MVP] All IP APIs failed');
                showGlobalFeedMessage();
                return;
            }

            const api = IP_GEOLOCATION_APIS[index];
            console.log(`[Geo MVP] Trying ${api.name}...`);

            fetch(api.url, {
                method: 'GET',
                headers: { 'Accept': 'application/json' }
            })
            .then(response => response.ok ? response.json() : Promise.reject(`HTTP ${response.status}`))
            .then(data => {
                const coords = api.parse(data);
                if (coords && coords.lat && coords.lon) {
                    console.log(`[Geo MVP] ${api.name} success:`, coords.lat, coords.lon);
                    saveIPLocation(coords.lat, coords.lon);
                } else {
                    console.log(`[Geo MVP] ${api.name} returned invalid data`);
                    tryIPAPI(index + 1);  // Try next API
                }
            })
            .catch(error => {
                console.log(`[Geo MVP] ${api.name} failed:`, error);
                tryIPAPI(index + 1);  // Try next API
            });
        }
    }

    /**
     * Save IP-based coordinates to server.
     */
    function saveIPLocation(latitude, longitude) {
        fetch('/api/geolocation/ip/update/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCSRFToken(),
                'X-Requested-With': 'XMLHttpRequest',
            },
            credentials: 'same-origin',
            body: JSON.stringify({ latitude, longitude })
        })
        .then(response => response.ok ? response.json() : Promise.reject('IP update failed'))
        .then(data => {
            if (data.success) {
                console.log('[Geo MVP] IP location saved, reloading...');
                // Set flag before reload to prevent infinite loop
                localStorage.setItem(GEO_JUST_UPDATED_KEY, Date.now().toString());
                window.location.reload();
            }
        })
        .catch(error => {
            console.error('[Geo MVP] Failed to save IP location:', error);
            showGlobalFeedMessage();
        });
    }

    /**
     * Record that user denied browser permission.
     */
    function recordPermissionDenied() {
        fetch('/api/geolocation/permission/denied/', {
            method: 'POST',
            headers: {
                'X-CSRFToken': getCSRFToken(),
                'X-Requested-With': 'XMLHttpRequest',
            },
            credentials: 'same-origin'
        })
        .then(() => console.log('[Geo MVP] Permission denial recorded'))
        .catch(error => console.error('[Geo MVP] Failed to record denial:', error));
    }

    /**
     * Show message suggesting Global feed when location fails.
     */
    function showGlobalFeedMessage() {
        console.log('[Geo MVP] Showing Global feed suggestion');
        // Could display a banner/toast here if desired
        // For MVP, Local feed still shows but without location-based ranking
    }

    // Initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

    // Export for external access
    window.FeedScroll = {
        refresh: initViewTracking,
        loadMore: loadMoreContent,
    };

})();
