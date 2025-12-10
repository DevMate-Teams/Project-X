/**
 * Feed Infinite Scroll & View Tracking
 * 
 * Implements:
 * - Infinite scroll pagination for home feed
 * - Log view tracking for feed freshness calculation
 * - Intersection Observer for detecting visible logs
 */

(function () {
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
    // Browser-Only Geolocation System for Local Feed
    // ==========================================================================
    //
    // RULES:
    // 1. ONLY browser geolocation is used (no IP fallback)
    // 2. 24 hour freshness window
    // 3. If denied: show message, no fallback
    //
    // ==========================================================================

    // LocalStorage key to prevent redundant location checks
    const GEO_JUST_UPDATED_KEY = 'geo_just_updated';
    const GEO_UPDATE_COOLDOWN_MS = 5000; // 5 seconds cooldown after update

    /**
     * Initialize geolocation for Local feed.
     * Only runs on Local tab.
     */
    function initGeolocation() {
        // Only run on Local feed
        if (getFeedTypeFromURL() !== 'local') {
            return;
        }

        // Prevent redundant checks after location update
        const justUpdated = localStorage.getItem(GEO_JUST_UPDATED_KEY);
        if (justUpdated) {
            const timeSinceUpdate = Date.now() - parseInt(justUpdated);
            if (timeSinceUpdate < GEO_UPDATE_COOLDOWN_MS) {
                console.log('[Geo] Just updated location, skipping check');
                localStorage.removeItem(GEO_JUST_UPDATED_KEY);
                return;
            }
            localStorage.removeItem(GEO_JUST_UPDATED_KEY);
        }

        console.log('[Geo] Initializing geolocation for Local feed...');

        // Fetch server status
        fetch('/api/geolocation/status/', {
            method: 'GET',
            headers: { 'X-Requested-With': 'XMLHttpRequest' },
            credentials: 'same-origin'
        })
            .then(response => response.ok ? response.json() : Promise.reject('Status fetch failed'))
            .then(status => {
                console.log('[Geo] Status:', status);
                executeGeolocation(status);
            })
            .catch(error => {
                console.error('[Geo] Status check failed:', error);
            });
    }

    /**
     * Execute geolocation based on server status.
     */
    function executeGeolocation(status) {
        const action = status.recommended_action;

        console.log('[Geo] Recommended action:', action);

        switch (action) {
            case 'use_location':
                // Location is fresh (< 24h), use it
                console.log('[Geo] Using fresh location');
                break;

            case 'request_location':
                // No location or stale - request from browser
                console.log('[Geo] Requesting browser location');
                requestBrowserLocation(false);
                break;

            case 'retry_request_location':
                // Previously denied - try again silently (user may have changed browser permission)
                console.log('[Geo] Retrying browser location (previously denied)');
                requestBrowserLocation(true);
                break;

            default:
                console.warn('[Geo] Unknown action:', action);
        }
    }

    /**
     * Request browser geolocation.
     * @param {boolean} isRetry - If true, this is a retry after previous denial (silent attempt)
     * @param {number} attempt - Current attempt number for timeout retry
     */
    function requestBrowserLocation(isRetry = false, attempt = 1) {
        const MAX_ATTEMPTS = 2;
        const TIMEOUT_MS = 30000; // 30 seconds for GPS lock

        if (!navigator.geolocation) {
            console.log('[Geo] Browser geolocation not available');
            showEnableLocationMessage();
            return;
        }

        // Only show loading indicator for fresh requests, not retries
        if (!isRetry && attempt === 1) {
            showLocationLoadingIndicator();
        }

        navigator.geolocation.getCurrentPosition(
            // SUCCESS - User granted permission
            (position) => {
                const { latitude, longitude } = position.coords;
                console.log('[Geo] Got location:', latitude.toFixed(4), longitude.toFixed(4));
                saveLocation(latitude, longitude);
            },
            // ERROR
            (error) => {
                console.log('[Geo] Failed to get location:', error.message, '(code:', error.code + ')');

                // Error codes: 1=PERMISSION_DENIED, 2=POSITION_UNAVAILABLE, 3=TIMEOUT
                if (error.code === error.PERMISSION_DENIED) {
                    hideLocationLoadingIndicator();
                    if (!isRetry) {
                        recordPermissionDenied();
                    }
                    showEnableLocationMessage();
                } else if (error.code === error.TIMEOUT || error.code === error.POSITION_UNAVAILABLE) {
                    // Timeout or unavailable - retry once more
                    if (attempt < MAX_ATTEMPTS) {
                        console.log('[Geo] Retrying... (attempt', attempt + 1, 'of', MAX_ATTEMPTS + ')');
                        requestBrowserLocation(isRetry, attempt + 1);
                    } else {
                        // Max retries reached - show timeout message
                        hideLocationLoadingIndicator();
                        showTimeoutMessage();
                    }
                } else {
                    hideLocationLoadingIndicator();
                    showTimeoutMessage();
                }
            },
            {
                enableHighAccuracy: true,
                timeout: TIMEOUT_MS,
                maximumAge: 0  // Always get fresh position
            }
        );
    }

    /**
     * Show message when location times out (different from permission denied).
     */
    function showTimeoutMessage() {
        console.log('[Geo] Showing timeout message');

        const existing = document.getElementById('geo-timeout-message');
        if (existing) existing.remove();

        const message = document.createElement('div');
        message.id = 'geo-timeout-message';
        message.className = 'fixed bottom-4 left-1/2 transform -translate-x-1/2 z-50 bg-orange-900 text-orange-100 px-5 py-3 rounded-lg shadow-lg text-sm border border-orange-700 w-full max-w-sm sm:max-w-md md:max-w-lg';
        message.innerHTML = `
            <div class="flex items-center gap-3">
                <i class="fa fa-clock text-orange-400"></i>
                <span>Location request timed out. Please try again or check your GPS settings.</span>
                <button onclick="this.parentElement.parentElement.remove()" class="ml-2 text-orange-400 hover:text-orange-200">
                    <i class="fa fa-times"></i>
                </button>
            </div>
        `;
        document.body.appendChild(message);
    }

    /**
     * Save location to server.
     */
    function saveLocation(latitude, longitude) {
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
            .then(response => response.ok ? response.json() : Promise.reject('Update failed'))
            .then(data => {
                if (data.success) {
                    console.log('[Geo] Location saved, refreshing feed...');
                    localStorage.setItem(GEO_JUST_UPDATED_KEY, Date.now().toString());
                    refreshLocalFeed();
                }
            })
            .catch(error => {
                console.error('[Geo] Failed to save location:', error);
                hideLocationLoadingIndicator();
            });
    }

    /**
     * Record permission denial on server.
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
            .then(() => console.log('[Geo] Permission denial recorded'))
            .catch(error => console.error('[Geo] Failed to record denial:', error));
    }

    /**
     * Refresh Local feed content via AJAX.
     */
    function refreshLocalFeed() {
        const feedContainer = document.getElementById('feed-container');
        if (!feedContainer) {
            window.location.reload();
            return;
        }

        console.log('[Geo] Refreshing feed...');

        fetch('/?feed=local', {
            method: 'GET',
            headers: { 'X-Requested-With': 'XMLHttpRequest' },
            credentials: 'same-origin'
        })
            .then(response => response.text())
            .then(html => {
                const parser = new DOMParser();
                const doc = parser.parseFromString(html, 'text/html');
                const newFeedContainer = doc.getElementById('feed-container');

                if (newFeedContainer) {
                    feedContainer.innerHTML = newFeedContainer.innerHTML;
                    feedContainer.dataset.nextCursor = newFeedContainer.dataset.nextCursor || '';
                    feedContainer.dataset.hasNext = newFeedContainer.dataset.hasNext || 'False';
                    initViewTracking();

                    if (typeof hljs !== 'undefined') {
                        feedContainer.querySelectorAll('pre code:not(.hljs)').forEach((block) => {
                            hljs.highlightElement(block);
                        });
                    }

                    console.log('[Geo] Feed refreshed');
                }

                hideLocationLoadingIndicator();
            })
            .catch(error => {
                console.error('[Geo] Feed refresh failed:', error);
                window.location.reload();
            });
    }

    /**
     * Show loading indicator.
     */
    function showLocationLoadingIndicator() {
        let indicator = document.getElementById('geo-loading-indicator');
        if (!indicator) {
            indicator = document.createElement('div');
            indicator.id = 'geo-loading-indicator';
            indicator.className = 'fixed top-4 left-1/2 transform -translate-x-1/2 z-50 bg-gray-800 text-white px-4 py-2 rounded-lg shadow-lg flex items-center gap-2';
            indicator.innerHTML = `
                <div class="w-4 h-4 border-2 border-green-500 border-t-transparent rounded-full animate-spin"></div>
                <span class="text-sm">Getting your location...</span>
            `;
            document.body.appendChild(indicator);
        }
        indicator.classList.remove('hidden');
    }

    /**
     * Hide loading indicator.
     */
    function hideLocationLoadingIndicator() {
        const indicator = document.getElementById('geo-loading-indicator');
        if (indicator) {
            indicator.classList.add('hidden');
        }
    }

    /**
     * Show message when location is not enabled.
     */
    function showEnableLocationMessage() {
        console.log('[Geo] Showing enable location message');
        hideLocationLoadingIndicator();

        // Remove any existing message
        const existing = document.getElementById('geo-enable-message');
        if (existing) existing.remove();

        // Show persistent message
        const message = document.createElement('div');
        message.id = 'geo-enable-message';
        message.className = 'fixed bottom-4 left-1/2 transform -translate-x-1/2 z-50 bg-yellow-900 text-yellow-100 px-5 py-3 rounded-lg shadow-lg text-sm border border-yellow-700 w-full max-w-sm sm:max-w-md md:max-w-lg';
        message.innerHTML = `
            <div class="flex items-center gap-3">
                <i class="fa fa-location-arrow text-yellow-400"></i>
                <span>Please enable location access to view your local feed.</span>
                <button onclick="this.parentElement.parentElement.remove()" class="ml-2 text-yellow-400 hover:text-yellow-200">
                    <i class="fa fa-times"></i>
                </button>
            </div>
        `;
        document.body.appendChild(message);
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
