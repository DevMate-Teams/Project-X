/**
 * Real-time notification polling system
 * Polls the server every 30 seconds for new notifications
 */

let notificationPollInterval = null;
let lastNotificationCount = 0;

// Initialize notification polling when DOM is ready
document.addEventListener('DOMContentLoaded', function () {
    if (document.querySelector('.notification-badge')) {
        initializeNotificationPolling();
    }
});

/**
 * Start polling for notifications
 */
function initializeNotificationPolling() {
    // Initial fetch
    fetchNotificationCount();

    // Poll every 30 seconds
    notificationPollInterval = setInterval(fetchNotificationCount, 30000);
}

/**
 * Fetch notification count from server
 */
async function fetchNotificationCount() {
    try {
        const response = await fetch('/notifications/count/');
        const data = await response.json();

        updateNotificationBadge(data.count);

        // Optional: Show desktop notification for new notifications
        if (data.count > lastNotificationCount && lastNotificationCount > 0) {
            showNewNotificationAlert(data.count - lastNotificationCount);
        }

        lastNotificationCount = data.count;
    } catch (error) {
        console.error('Error fetching notification count:', error);
    }
}

/**
 * Update the notification badge in the UI
 */
function updateNotificationBadge(count) {
    const badge = document.querySelector('.notification-badge');

    if (!badge) return;

    if (count > 0) {
        badge.textContent = count > 99 ? '99+' : count;
        badge.classList.remove('hidden');
        badge.classList.add('animate-pulse');

        // Remove pulse animation after 2 seconds
        setTimeout(() => {
            badge.classList.remove('animate-pulse');
        }, 2000);
    } else {
        badge.classList.add('hidden');
    }
}

/**
 * Show a subtle alert for new notifications (optional)
 */
function showNewNotificationAlert(newCount) {
    // You can implement a toast notification here
    console.log(`You have ${newCount} new notification(s)`);

    // Optional: Browser notification (requires permission)
    if ('Notification' in window && Notification.permission === 'granted') {
        new Notification('DevMate', {
            body: `You have ${newCount} new notification(s)`,
            icon: '/static/assets/logo.png',
            badge: '/static/assets/logo.png'
        });
    }
}

/**
 * Mark all notifications as read
 */
async function markAllNotificationsRead() {
    try {
        const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value
            || getCookie('csrftoken');

        const response = await fetch('/notifications/mark-all-read/', {
            method: 'POST',
            headers: {
                'X-CSRFToken': csrfToken,
                'Content-Type': 'application/json'
            }
        });

        const data = await response.json();

        if (data.success) {
            // Update UI
            updateNotificationBadge(0);

            // Mark all notification items as read in the UI
            document.querySelectorAll('.notification-item.unread').forEach(item => {
                item.classList.remove('unread', 'bg-[#20252d]');
            });

            // Optionally reload the page or update the count display
            location.reload();
        }
    } catch (error) {
        console.error('Error marking notifications as read:', error);
    }
}

/**
 * Mark a single notification as read
 */
async function markNotificationRead(notificationId) {
    try {
        const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value
            || getCookie('csrftoken');

        const response = await fetch(`/notifications/${notificationId}/mark-read/`, {
            method: 'POST',
            headers: {
                'X-CSRFToken': csrfToken,
                'Content-Type': 'application/json'
            }
        });

        const data = await response.json();

        if (data.success) {
            // Update the specific notification item
            const notificationItem = document.querySelector(`[data-notification-id="${notificationId}"]`);
            if (notificationItem) {
                notificationItem.classList.remove('unread', 'bg-[#20252d]');
            }

            // Refresh count
            fetchNotificationCount();
        }
    } catch (error) {
        console.error('Error marking notification as read:', error);
    }
}

/**
 * Request browser notification permission
 */
function requestNotificationPermission() {
    if ('Notification' in window && Notification.permission === 'default') {
        Notification.requestPermission();
    }
}

/**
 * Helper function to get CSRF cookie
 */
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

// Stop polling when page is hidden (battery saving)
document.addEventListener('visibilitychange', function () {
    if (document.hidden) {
        if (notificationPollInterval) {
            clearInterval(notificationPollInterval);
        }
    } else {
        if (document.querySelector('.notification-badge')) {
            initializeNotificationPolling();
        }
    }
});
