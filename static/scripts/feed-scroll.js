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
    
    // LocalStorage keys for geolocation state
    const GEO_STATE = {
        PERMISSION_DENIED: 'geo_permission_denied',      // User denied browser permission
        LOCATION_UPDATED: 'geo_location_updated',        // Location was just updated (prevent reload loop)
        LAST_PROMPT: 'geo_last_prompt',                  // Last time we prompted for location
    };
    
    // Cooldown periods (in milliseconds)
    const GEO_COOLDOWNS = {
        AFTER_UPDATE: 30 * 1000,           // 30 seconds after successful update
        AFTER_DENIAL: 24 * 60 * 60 * 1000, // 24 hours after permission denied
        BETWEEN_PROMPTS: 5 * 60 * 1000,    // 5 minutes between prompts
    };

    /**
     * Clean up stale geolocation localStorage entries.
     * Removes keys that have exceeded their cooldown period.
     */
    function cleanupStaleGeoState() {
        const now = Date.now();
        
        // Clean up LOCATION_UPDATED if past cooldown
        const lastUpdated = localStorage.getItem(GEO_STATE.LOCATION_UPDATED);
        if (lastUpdated && (now - parseInt(lastUpdated)) >= GEO_COOLDOWNS.AFTER_UPDATE) {
            localStorage.removeItem(GEO_STATE.LOCATION_UPDATED);
        }
        
        // Clean up PERMISSION_DENIED if past cooldown
        const deniedAt = localStorage.getItem(GEO_STATE.PERMISSION_DENIED);
        if (deniedAt && (now - parseInt(deniedAt)) >= GEO_COOLDOWNS.AFTER_DENIAL) {
            localStorage.removeItem(GEO_STATE.PERMISSION_DENIED);
        }
        
        // Clean up LAST_PROMPT if past cooldown
        const lastPrompt = localStorage.getItem(GEO_STATE.LAST_PROMPT);
        if (lastPrompt && (now - parseInt(lastPrompt)) >= GEO_COOLDOWNS.BETWEEN_PROMPTS) {
            localStorage.removeItem(GEO_STATE.LAST_PROMPT);
        }
    }

    function initGeolocation() {
        const feedType = getFeedTypeFromURL();
        
        // Always clean up stale entries (runs on any page)
        cleanupStaleGeoState();
        
        // Only run geolocation logic on Local tab
        if (feedType !== 'local') {
            return;
        }
        
        console.log('Local tab detected, checking geolocation status...');
        
        // Check if we just updated location (prevent reload loop)
        const lastUpdated = localStorage.getItem(GEO_STATE.LOCATION_UPDATED);
        if (lastUpdated && (Date.now() - parseInt(lastUpdated)) < GEO_COOLDOWNS.AFTER_UPDATE) {
            console.log('Location recently updated, skipping check to prevent loop');
            localStorage.removeItem(GEO_STATE.LOCATION_UPDATED);  // Clear flag
            return;
        }
        
        // Check if user denied permission recently
        const deniedAt = localStorage.getItem(GEO_STATE.PERMISSION_DENIED);
        if (deniedAt && (Date.now() - parseInt(deniedAt)) < GEO_COOLDOWNS.AFTER_DENIAL) {
            console.log('Permission was denied recently, skipping browser prompt');
            return;
        }
        
        // Check rate limit between prompts
        const lastPrompt = localStorage.getItem(GEO_STATE.LAST_PROMPT);
        if (lastPrompt && (Date.now() - parseInt(lastPrompt)) < GEO_COOLDOWNS.BETWEEN_PROMPTS) {
            console.log('Rate limited: too soon since last prompt');
            return;
        }
        
        checkAndRefreshGeolocation();
    }

    function checkAndRefreshGeolocation() {
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
            console.log('Geolocation status:', data);
            
            // Location is current - no action needed
            if (data.has_location && !data.needs_refresh) {
                console.log('Location is current:', data.city, data.state);
                return;
            }
            
            console.log('Location needs refresh, requesting browser geolocation...');
            localStorage.setItem(GEO_STATE.LAST_PROMPT, Date.now().toString());
            requestBrowserGeolocation();
        })
        .catch(error => {
            console.error('Error checking geolocation status:', error);
            // Don't spam on errors - just log and continue
        });
    }

    function requestBrowserGeolocation() {
        // Check if Geolocation API is available
        if (!navigator.geolocation) {
            console.log('Geolocation API not supported, using IP fallback');
            triggerIPFallback();
            return;
        }

        // localhost is considered secure context, so only check for non-localhost
        const isLocalhost = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
        if (!window.isSecureContext && !isLocalhost) {
            console.log('Requires HTTPS (not localhost), using IP fallback');
            triggerIPFallback();
            return;
        }

        console.log('Requesting browser geolocation permission...');

        navigator.geolocation.getCurrentPosition(
            (position) => {
                // Success - clear any denial flag and send to server
                localStorage.removeItem(GEO_STATE.PERMISSION_DENIED);
                const { latitude, longitude } = position.coords;
                console.log('Got browser location:', latitude, longitude);
                updateServerGeolocation(latitude, longitude);
            },
            (error) => {
                console.log('Geolocation error:', error.code, error.message);
                
                if (error.code === error.PERMISSION_DENIED) {
                    // User denied - remember this to avoid re-prompting
                    console.log('Permission denied, will not prompt again for 24 hours');
                    localStorage.setItem(GEO_STATE.PERMISSION_DENIED, Date.now().toString());
                }
                
                // All errors fall back to IP geolocation
                triggerIPFallback();
            },
            {
                enableHighAccuracy: true,
                timeout: 10000,
                maximumAge: 0
            }
        );
    }

    function triggerIPFallback() {
        /**
         * Server-side IP geolocation fallback.
         * In development, server uses configured fallback coordinates.
         * In production, server uses real IP geolocation APIs.
         */
        console.log('Triggering IP-based geolocation fallback...');
        
        fetch('/api/geolocation/ip-fallback/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCSRFToken(),
                'X-Requested-With': 'XMLHttpRequest',
            },
            credentials: 'same-origin'
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                console.log('IP fallback successful:', data.city, data.state, data.country);
                // Mark that we just updated (prevents reload loop)
                localStorage.setItem(GEO_STATE.LOCATION_UPDATED, Date.now().toString());
                // Reload to show local feed with new location
                if (getFeedTypeFromURL() === 'local') {
                    window.location.reload();
                }
            } else {
                console.warn('IP fallback failed:', data.error);
                // Don't retry - just continue without location-based ranking
            }
        })
        .catch(error => {
            console.error('Error in IP fallback:', error);
        });
    }

    function updateServerGeolocation(latitude, longitude) {
        fetch('/api/geolocation/update/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCSRFToken(),
            },
            body: JSON.stringify({ latitude, longitude })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                console.log('Browser geolocation saved successfully');
                // Mark that we just updated (prevents reload loop)
                localStorage.setItem(GEO_STATE.LOCATION_UPDATED, Date.now().toString());
                // Reload to show local feed with new location
                if (getFeedTypeFromURL() === 'local') {
                    window.location.reload();
                }
            } else {
                console.error('Failed to save geolocation:', data.error);
            }
        })
        .catch(error => {
            console.error('Error saving geolocation:', error);
        });
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
