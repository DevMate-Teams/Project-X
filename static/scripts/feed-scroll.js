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
    let currentPage = 1;
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
        if (isLoading || !hasMoreContent) return;

        isLoading = true;
        const loadingIndicator = document.getElementById('loading');
        const feedContainer = document.getElementById('feed-container');

        if (loadingIndicator) {
            loadingIndicator.classList.remove('hidden');
        }

        currentPage++;

        fetch(`/load-more-feed/?page=${currentPage}&feed=${currentFeedType}`, {
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

            hasMoreContent = data.has_next;

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
            currentPage--; // Revert page increment on error
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
    // Browser Geolocation (for Local feed accuracy)
    // ==========================================================================
    // 
    // WORKFLOW:
    // START → User opens Local Feed
    //        ↓
    // Browser location fresh? (within 7 days)
    //        ↓ Yes → Use existing location → END
    //        ↓ No
    // User previously denied? (within 24 hours)
    //        ↓ Yes → Use IP location (don't prompt) → END  
    //        ↓ No
    // Ask browser permission
    //      ↓        ↓
    //    Allow     Deny/Fail
    //      ↓        ↓
    // Update browser   Force update IP
    // timestamp        timestamp
    //      ↓        ↓
    // Use browser   Use IP → END
    // location
    //      ↓
    //    END
    //
    // ==========================================================================
    
    // LocalStorage keys for geolocation state management
    const GEO_STATE = {
        PERMISSION_DENIED: 'geo_permission_denied',   // Timestamp when user denied browser permission
        LOCATION_UPDATED: 'geo_location_updated',    // Timestamp when location was last updated (prevents reload loop)
        IP_FALLBACK_DONE: 'geo_ip_fallback_done',    // Timestamp when IP fallback was completed
    };
    
    // Cooldown periods (in milliseconds)
    const GEO_COOLDOWNS = {
        AFTER_UPDATE: 30 * 1000,            // 30 seconds - prevents reload loop after update
        AFTER_DENIAL: 24 * 60 * 60 * 1000,  // 24 hours - don't re-prompt after denial
        IP_FALLBACK: 60 * 60 * 1000,        // 1 hour - don't retry IP fallback too often
    };

    /**
     * Clean up expired geolocation localStorage entries.
     * Called on every page load to prevent stale data accumulation.
     */
    function cleanupExpiredGeoState() {
        const now = Date.now();
        
        Object.entries({
            [GEO_STATE.LOCATION_UPDATED]: GEO_COOLDOWNS.AFTER_UPDATE,
            [GEO_STATE.PERMISSION_DENIED]: GEO_COOLDOWNS.AFTER_DENIAL,
            [GEO_STATE.IP_FALLBACK_DONE]: GEO_COOLDOWNS.IP_FALLBACK,
        }).forEach(([key, maxAge]) => {
            const timestamp = localStorage.getItem(key);
            if (timestamp && (now - parseInt(timestamp)) >= maxAge) {
                localStorage.removeItem(key);
            }
        });
    }

    /**
     * Check if a localStorage timestamp is within its cooldown period.
     */
    function isWithinCooldown(key, cooldownMs) {
        const timestamp = localStorage.getItem(key);
        if (!timestamp) return false;
        return (Date.now() - parseInt(timestamp)) < cooldownMs;
    }

    /**
     * Initialize geolocation for Local feed.
     * Entry point called on page load.
     */
    function initGeolocation() {
        // Always clean up expired entries on any page
        cleanupExpiredGeoState();
        
        // Only run geolocation logic on Local tab
        if (getFeedTypeFromURL() !== 'local') {
            return;
        }
        
        console.log('[Geo] Local tab detected, checking geolocation status...');
        
        // GUARD: Prevent reload loop - if we just updated, skip
        if (isWithinCooldown(GEO_STATE.LOCATION_UPDATED, GEO_COOLDOWNS.AFTER_UPDATE)) {
            console.log('[Geo] Location recently updated, skipping to prevent loop');
            localStorage.removeItem(GEO_STATE.LOCATION_UPDATED); // Clear after check
            return;
        }
        
        // Fetch server status and decide what to do
        checkGeolocationStatus();
    }

    /**
     * Check server for current geolocation status and decide action.
     */
    function checkGeolocationStatus() {
        fetch('/api/geolocation/status/', {
            method: 'GET',
            headers: { 'X-Requested-With': 'XMLHttpRequest' },
            credentials: 'same-origin'
        })
        .then(response => {
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            return response.json();
        })
        .then(data => {
            console.log('[Geo] Server status:', data);
            handleGeolocationDecision(data);
        })
        .catch(error => {
            console.error('[Geo] Error checking status:', error);
            // On network error, don't do anything - user still sees feed
        });
    }

    /**
     * Core decision logic based on server status.
     * Implements the workflow flowchart.
     */
    function handleGeolocationDecision(serverStatus) {
        const { has_location, needs_refresh, browser_updated_at } = serverStatus;
        
        // CASE 1: Browser location is fresh → Use existing location, done
        if (has_location && !needs_refresh && browser_updated_at) {
            console.log('[Geo] Browser location is fresh:', serverStatus.city, serverStatus.state);
            return;
        }
        
        // CASE 2: User previously denied permission → Use IP (don't prompt browser)
        if (isWithinCooldown(GEO_STATE.PERMISSION_DENIED, GEO_COOLDOWNS.AFTER_DENIAL)) {
            console.log('[Geo] User denied permission recently');
            
            // If we already have IP location, use it
            if (has_location) {
                console.log('[Geo] Using existing IP location:', serverStatus.city);
                return;
            }
            
            // No location at all - try IP fallback (if not done recently)
            if (!isWithinCooldown(GEO_STATE.IP_FALLBACK_DONE, GEO_COOLDOWNS.IP_FALLBACK)) {
                console.log('[Geo] No location, triggering IP fallback');
                triggerIPFallback();
            }
            return;
        }
        
        // CASE 3: Need to prompt for browser location
        console.log('[Geo] Requesting browser geolocation...');
        requestBrowserGeolocation();
    }

    /**
     * Request browser geolocation permission.
     * On success: Update browser location.
     * On failure/denial: Fall back to IP geolocation.
     */
    function requestBrowserGeolocation() {
        // Check if Geolocation API is available
        if (!navigator.geolocation) {
            console.log('[Geo] Browser API not supported, using IP fallback');
            triggerIPFallback();
            return;
        }

        // Check secure context (localhost is considered secure)
        const isLocalhost = ['localhost', '127.0.0.1'].includes(window.location.hostname);
        if (!window.isSecureContext && !isLocalhost) {
            console.log('[Geo] Requires HTTPS, using IP fallback');
            triggerIPFallback();
            return;
        }

        console.log('[Geo] Prompting for browser permission...');

        navigator.geolocation.getCurrentPosition(
            // SUCCESS: User allowed permission
            (position) => {
                localStorage.removeItem(GEO_STATE.PERMISSION_DENIED); // Clear any old denial
                const { latitude, longitude } = position.coords;
                console.log('[Geo] Browser location received:', latitude.toFixed(4), longitude.toFixed(4));
                updateBrowserLocation(latitude, longitude);
            },
            // ERROR: User denied or other failure
            (error) => {
                console.log('[Geo] Browser error:', error.code, error.message);
                
                if (error.code === error.PERMISSION_DENIED) {
                    // Remember denial to avoid re-prompting for 24 hours
                    localStorage.setItem(GEO_STATE.PERMISSION_DENIED, Date.now().toString());
                    console.log('[Geo] Permission denied, will use IP fallback');
                }
                
                // All errors fall back to IP geolocation
                triggerIPFallback();
            },
            {
                enableHighAccuracy: true,
                timeout: 10000,
                maximumAge: 300000  // Accept cached position up to 5 minutes old
            }
        );
    }

    /**
     * Send browser coordinates to server.
     * Updates browser_location_updated_at timestamp.
     */
    function updateBrowserLocation(latitude, longitude) {
        fetch('/api/geolocation/update/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCSRFToken(),
                'X-Requested-With': 'XMLHttpRequest',
            },
            credentials: 'same-origin',
            body: JSON.stringify({ latitude, longitude })
        })
        .then(response => {
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            return response.json();
        })
        .then(data => {
            if (data.success) {
                console.log('[Geo] Browser location saved successfully');
                markLocationUpdatedAndReload();
            } else {
                console.error('[Geo] Server rejected browser location:', data.error);
                // Fall back to IP if browser update fails
                triggerIPFallback();
            }
        })
        .catch(error => {
            console.error('[Geo] Network error saving browser location:', error);
            // Fall back to IP on network error
            triggerIPFallback();
        });
    }

    /**
     * Trigger server-side IP geolocation.
     * Used when browser geolocation is unavailable or denied.
     * 
     * In development: Server uses GEOLOCATION_DEV_FALLBACK from settings.
     * In production: Server calls real IP geolocation APIs.
     */
    function triggerIPFallback() {
        // Don't retry IP fallback too frequently
        if (isWithinCooldown(GEO_STATE.IP_FALLBACK_DONE, GEO_COOLDOWNS.IP_FALLBACK)) {
            console.log('[Geo] IP fallback done recently, skipping');
            return;
        }
        
        console.log('[Geo] Triggering IP-based geolocation...');
        
        fetch('/api/geolocation/ip-fallback/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCSRFToken(),
                'X-Requested-With': 'XMLHttpRequest',
            },
            credentials: 'same-origin'
        })
        .then(response => {
            if (!response.ok) {
                // Server returned error status
                return response.json().then(data => {
                    throw new Error(data.error || `HTTP ${response.status}`);
                });
            }
            return response.json();
        })
        .then(data => {
            if (data.success) {
                console.log('[Geo] IP fallback successful:', data.city, data.state, data.country);
                // Mark IP fallback as done (prevents rapid retries)
                localStorage.setItem(GEO_STATE.IP_FALLBACK_DONE, Date.now().toString());
                markLocationUpdatedAndReload();
            } else {
                throw new Error(data.error || 'Unknown error');
            }
        })
        .catch(error => {
            console.warn('[Geo] IP fallback failed:', error.message);
            // Mark as attempted to prevent rapid retries
            localStorage.setItem(GEO_STATE.IP_FALLBACK_DONE, Date.now().toString());
            // User will see Local feed without location-based ranking
            // They can try again in 1 hour or on next browser location prompt in 24h
        });
    }

    /**
     * Mark location as updated and reload page.
     * The LOCATION_UPDATED flag prevents infinite reload loops.
     */
    function markLocationUpdatedAndReload() {
        localStorage.setItem(GEO_STATE.LOCATION_UPDATED, Date.now().toString());
        if (getFeedTypeFromURL() === 'local') {
            console.log('[Geo] Reloading Local feed with new location...');
            window.location.reload();
        }
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
