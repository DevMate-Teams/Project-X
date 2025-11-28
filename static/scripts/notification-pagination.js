/**
 * Notification Pagination - Load More functionality
 * Handles AJAX loading of additional notifications
 */

document.addEventListener('DOMContentLoaded', function () {
    const loadMoreBtn = document.getElementById('load-more-btn');
    const loadingSpinner = document.getElementById('loading-spinner');
    const notificationsContainer = document.getElementById('notifications-container');

    if (!loadMoreBtn) return; // No pagination needed

    loadMoreBtn.addEventListener('click', async function () {
        const nextPage = this.dataset.nextPage;

        if (!nextPage) return;

        // Show loading state
        loadMoreBtn.classList.add('hidden');
        loadingSpinner.classList.remove('hidden');

        try {
            const response = await fetch(`/notifications/load-more/?page=${nextPage}`);
            const data = await response.json();

            if (data.error) {
                console.error('Error loading notifications:', data.error);
                showErrorMessage();
                return;
            }

            // Append new notifications to container
            if (data.html) {
                const tempDiv = document.createElement('div');
                tempDiv.innerHTML = data.html;

                // Append each child to maintain structure
                while (tempDiv.firstChild) {
                    notificationsContainer.appendChild(tempDiv.firstChild);
                }
            }

            // Update button state
            if (data.has_more) {
                loadMoreBtn.dataset.nextPage = data.next_page;
                loadMoreBtn.classList.remove('hidden');
            } else {
                // No more notifications - show "all caught up" message
                showAllCaughtUpMessage();
            }

        } catch (error) {
            console.error('Error loading more notifications:', error);
            showErrorMessage();
            loadMoreBtn.classList.remove('hidden');
        } finally {
            loadingSpinner.classList.add('hidden');
        }
    });
});

/**
 * Show "All caught up" message when no more notifications
 */
function showAllCaughtUpMessage() {
    const loadingSpinner = document.getElementById('loading-spinner');
    const parent = loadingSpinner.parentElement;

    parent.innerHTML = `
        <div class="flex flex-col items-center gap-2 py-4">
            <i class="fa-solid fa-check-circle text-2xl text-green-500"></i>
            <p class="text-sm text-[#7d8590] font-medium">All caught up!</p>
        </div>
    `;
}

/**
 * Show error message if loading fails
 */
function showErrorMessage() {
    const loadingSpinner = document.getElementById('loading-spinner');
    loadingSpinner.innerHTML = `
        <div class="flex items-center gap-2 text-red-500">
            <i class="fa-solid fa-exclamation-circle"></i>
            <span class="text-sm">Failed to load notifications. Please refresh the page.</span>
        </div>
    `;
    loadingSpinner.classList.remove('hidden');
}
