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
    function initGeolocation() {
        const feedType = getFeedTypeFromURL();
        
        // On Local tab, always check if we need to refresh location
        if (feedType === 'local') {
            console.log('Local tab detected, checking geolocation status...');
            checkAndRefreshGeolocation();
        }
    }

    function checkAndRefreshGeolocation() {
        // Check server for current geolocation status
        fetch('/api/geolocation/status/', {
            method: 'GET',
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
            },
            credentials: 'same-origin'  // Ensure cookies are sent
        })
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            return response.json();
        })
        .then(data => {
            console.log('Geolocation status:', data);
            
            // Request browser location if:
            // 1. No location set, OR
            // 2. Location is stale (needs_refresh = true)
            if (!data.has_location || data.needs_refresh) {
                console.log('Location needs refresh, requesting browser geolocation...');
                requestBrowserGeolocation();
            } else {
                console.log('Location is current:', data.city, data.state);
            }
        })
        .catch(error => {
            console.error('Error checking geolocation status:', error);
            // On error, try to request geolocation anyway for new users
            // Use a simple rate limit to avoid spamming
            tryFallbackGeolocation();
        });
    }

    function tryFallbackGeolocation() {
        // Fallback: Check localStorage for last request time
        const lastRequest = localStorage.getItem('geolocation_last_request');
        const hourAgo = Date.now() - (60 * 60 * 1000);  // 1 hour rate limit
        
        if (!lastRequest || parseInt(lastRequest) < hourAgo) {
            console.log('Fallback: Requesting geolocation due to API error');
            requestBrowserGeolocation();
        } else {
            console.log('Fallback: Rate limited, last request was recent');
        }
    }

    function requestBrowserGeolocation() {
        // Check if Geolocation API is available
        if (!navigator.geolocation) {
            console.log('Geolocation not supported by browser, using IP fallback');
            triggerIPFallback();
            return;
        }

        // Check if we're in a secure context (required for geolocation)
        if (!window.isSecureContext) {
            console.log('Geolocation requires secure context (HTTPS), using IP fallback');
            triggerIPFallback();
            return;
        }

        console.log('Requesting browser geolocation permission...');
        
        // Update last request timestamp
        localStorage.setItem('geolocation_last_request', Date.now().toString());

        // Request position with high accuracy
        navigator.geolocation.getCurrentPosition(
            (position) => {
                // Success - send coordinates to server
                const { latitude, longitude } = position.coords;
                console.log('Got browser location:', latitude, longitude);
                updateServerGeolocation(latitude, longitude);
            },
            (error) => {
                // Handle specific error cases and trigger IP fallback
                switch (error.code) {
                    case error.PERMISSION_DENIED:
                        console.log('Geolocation permission denied by user, triggering IP fallback');
                        triggerIPFallback();
                        break;
                    case error.POSITION_UNAVAILABLE:
                        console.log('Geolocation position unavailable, triggering IP fallback');
                        triggerIPFallback();
                        break;
                    case error.TIMEOUT:
                        console.log('Geolocation request timed out, triggering IP fallback');
                        triggerIPFallback();
                        break;
                    default:
                        console.log('Geolocation error:', error.message, 'triggering IP fallback');
                        triggerIPFallback();
                }
            },
            {
                enableHighAccuracy: true,
                timeout: 15000,  // Increased timeout for slower connections
                maximumAge: 0    // Always get fresh position, don't use cached
            }
        );
    }

    function triggerIPFallback() {
        /**
         * Call server to set location via IP geolocation.
         * Used when browser geolocation is unavailable or denied.
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
                console.log('IP fallback successful:', data.city, data.state);
                // Refresh Local feed to show results based on IP location
                if (getFeedTypeFromURL() === 'local') {
                    window.location.reload();
                }
            } else {
                console.error('IP fallback failed:', data.error);
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
                console.log('Geolocation updated successfully');
                // Optionally refresh the Local feed if we're on it
                if (getFeedTypeFromURL() === 'local') {
                    window.location.reload();
                }
            }
        })
        .catch(error => {
            console.error('Error updating geolocation:', error);
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
