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

//For Deleting logs - Works for both prefetched and dynamically loaded logs
document.addEventListener("DOMContentLoaded", function () {
  // Use event delegation on document for dynamic content
  $(document).on('click', '.delete-log-btn', function (e) {
    e.preventDefault();
    const button = $(this);
    const sig = button.data('log-id'); // Read from data-log-id attribute

    if (!sig) {
      console.error('No log signature found');
      alert('Error: Cannot identify the log to delete.');
      return;
    }

    // Find parent log card - look for the container with border-[#21262d]
    const logCard = button.closest('.border-\\[\\#21262d\\]');

    if (!confirm("Are you sure you want to delete this log?")) return;

    $.ajax({
      type: "POST",
      url: `/logs/delete-log/${sig}/`,
      headers: {
        "X-CSRFToken": getCSRFToken(),
      },
      success: function (response) {
        if (response.success) {
          logCard.fadeOut(400, function () {
            $(this).remove();
          });
          // Show success message (optional)
          console.log("Log deleted successfully!");
        } else {
          alert("Failed to delete the log.");
        }
      },
      error: function (xhr) {
        if (xhr.status === 403) {
          alert("Unauthorized: You can only delete your own logs.");
        } else if (xhr.status === 404) {
          alert("Log not found.");
        } else {
          alert("An error occurred. Please try again.");
        }
      }
    });
  });

  // Prevent duplicate log submissions
  const logForm = document.getElementById('log-section');
  if (logForm) {
    let isSubmitting = false;
    let submitBtn = null;
    let originalText = '';

    logForm.addEventListener('submit', function (e) {
      // Prevent duplicate submissions
      if (isSubmitting) {
        e.preventDefault();
        return false;
      }

      // Get the submit button
      submitBtn = logForm.querySelector('button[type="submit"]');
      
      if (!submitBtn) {
        return; // No submit button found, allow normal form submission
      }

      // Store original button text if not already stored
      if (!originalText) {
        originalText = submitBtn.innerHTML;
      }

      // Check if content field has value
      const contentInput = logForm.querySelector('#log-input');
      if (contentInput && !contentInput.value.trim()) {
        // Empty content, don't submit
        return;
      }

      // Check if form has HTML5 validation errors
      if (!logForm.checkValidity()) {
        // Let browser handle validation display
        return;
      }

      // Mark as submitting
      isSubmitting = true;

      // Disable the button and show loading state
      submitBtn.disabled = true;
      submitBtn.innerHTML = '<i class="fa fa-spinner fa-spin"></i> Saving...';

      // Re-enable after timeout as fallback
      // This handles cases where:
      // 1. Server returns validation errors without redirect
      // 2. Network failures prevent submission
      // 3. Any other unexpected errors
      setTimeout(function () {
        if (isSubmitting && submitBtn) {
          isSubmitting = false;
          submitBtn.disabled = false;
          submitBtn.innerHTML = originalText;
        }
      }, 10000); // 10 seconds to account for slow connections
    });

    // Handle page visibility change (user switches tabs during submission)
    document.addEventListener('visibilitychange', function () {
      if (document.visibilityState === 'visible' && isSubmitting && submitBtn) {
        // Check if we're still on the same page after 1 second
        setTimeout(function () {
          if (isSubmitting && submitBtn && document.getElementById('log-section')) {
            // Still on same page, likely a validation error occurred
            isSubmitting = false;
            submitBtn.disabled = false;
            submitBtn.innerHTML = originalText;
          }
        }, 1000);
      }
    });

    // Handle beforeunload event to detect successful navigation
    window.addEventListener('beforeunload', function () {
      // If navigating away, the form likely submitted successfully
      // Keep button disabled during navigation
      if (isSubmitting) {
        // Keep button disabled during navigation
      }
    });
  }
});


//for log entry (code snippet and image)
function handle_log_ImageUpload(event) {
  const file = event.target.files[0];
  if (file) {
    const reader = new FileReader();
    reader.onload = function (e) {
      document.getElementById('imagePreview').src = e.target.result;
      document.getElementById('imagePreviewContainer').classList.remove('hidden');
    };
    reader.readAsDataURL(file);
  }
}

function remove_log_Image() {
  document.getElementById('snapshotInput').value = "";
  document.getElementById('imagePreviewContainer').classList.add('hidden');
}

function toggleCodeSnippet() {
  const container = document.getElementById('codeSnippetContainer');
  container.classList.toggle('hidden');
}

function toggleLinkInput() {
  const container = document.getElementById('linkInputContainer');
  container.classList.toggle('hidden');
}


/**
 * Cursor-Based AJAX Load More Logs for User Profile Page
 */
document.addEventListener("DOMContentLoaded", function () {
  // Use event delegation on document for dynamic content
  $(document).on('click', '#load-more-profile-logs', function () {
    const btn = $(this);
    const username = btn.data('username');
    const cursor = btn.data('cursor');

    // Show loading state
    const originalText = btn.html();
    btn.html('<i class="fa fa-spinner fa-spin"></i> Loading...');
    btn.prop('disabled', true);

    $.ajax({
      url: `/logs/load-more-profile-logs/${username}/`,
      type: 'GET',
      data: { cursor: cursor },
      success: function (response) {
        if (response.logs_html && response.logs_html.trim() !== '') {
          // Append new logs to container
          $('#log-container').append(response.logs_html);

          // Update cursor for next load
          if (response.cursor) {
            btn.data('cursor', response.cursor);
          }

          // If no more logs, hide the button with smooth animation
          if (!response.has_next) {
            btn.parent().fadeOut(300, function () {
              $(this).remove();
            });
          } else {
            // Restore button
            btn.html(originalText);
            btn.prop('disabled', false);
          }
        } else {
          // No more logs
          btn.parent().fadeOut(300, function () {
            $(this).remove();
          });
        }
      },
      error: function (xhr, status, error) {
        console.error('Error loading more logs:', error);
        console.error('Response:', xhr.responseText);
        btn.html(originalText);
        btn.prop('disabled', false);

        // Show user-friendly error message
        const errorMsg = $('<div class="text-red-400 text-xs mt-2 text-center">Failed to load logs. Please try again.</div>');
        btn.parent().append(errorMsg);
        setTimeout(() => errorMsg.fadeOut(300, function () { $(this).remove(); }), 3000);
      }
    });
  });
});

/**
 * Toggle reaction picker visibility
 */
function toggleReactionPicker(sig) {
  const picker = $(`#picker-${sig}`);
  const isHidden = picker.hasClass('hidden');

  // Close all pickers and remove listeners
  $('.reaction-picker').addClass('hidden');
  $(document).off('click.reactionPicker');

  if (isHidden) {
    picker.removeClass('hidden');

    // Delay attachment to avoid catching the current click
    setTimeout(() => {
      $(document).on('click.reactionPicker', function (e) {
        // If clicked outside the picker
        if (!$(e.target).closest(`#picker-${sig}`).length) {
          picker.addClass('hidden');
          $(document).off('click.reactionPicker');
        }
      });
    }, 0);
  }
}

/**
 * Toggle reaction on a log
 */
function toggleReaction(sig, emoji) {
  // Close picker if open and remove listener
  $(`#picker-${sig}`).addClass('hidden');
  $(document).off('click.reactionPicker');

  $.ajax({
    type: "POST",
    url: `/logs/reaction/${sig}/`,
    data: {
      'emoji': emoji,
      'csrfmiddlewaretoken': getCSRFToken()
    },
    success: function (response) {
      // Update UI based on response
      const container = $(`#reactions-${sig}`);

      // We need to update specific emoji button in the active list
      // Since we are now using separate buttons for each emoji in the list

      // Iterate through all 4 supported emojis to update their state
      ['❤️', '🚀', '💡', '😢'].forEach(e => {
        const count = response.counts[e] || 0;
        let btn = container.find(`.reaction-btn[data-emoji="${e}"]`);

        if (count > 0) {
          // If button doesn't exist (was hidden), we might need to show it
          // But in our template we render all and hide them.
          btn.removeClass('hidden');
          btn.find('.count').text(count);

          // Update style based on user reaction
          if (response.user_reaction === e) {
            btn.removeClass('bg-[#0d1117] text-gray-500 border border-[#21262d] hover:border-gray-600 hover:text-gray-300')
              .addClass('bg-blue-500/10 text-blue-400 border-blue-500/30');
          } else {
            btn.removeClass('bg-blue-500/10 text-blue-400 border-blue-500/30')
              .addClass('bg-[#0d1117] text-gray-500 border border-[#21262d] hover:border-gray-600 hover:text-gray-300');
          }
        } else {
          // Hide button if count is 0
          btn.addClass('hidden');
        }
      });
    },
    error: function (xhr) {
      console.error('Error toggling reaction:', xhr.responseText);
    }
  });
}

// Make functions globally available
window.toggleReaction = toggleReaction;
window.toggleReactionPicker = toggleReactionPicker;

/**
 * Toggle comments section visibility
 */
function toggleComments(sig) {
  const container = $(`#comments-container-${sig}`);
  container.toggleClass('hidden');
}

/**
 * Add a comment or reply to a log
 */
function addComment(event, sig, parentId = null) {
  event.preventDefault();

  const inputId = parentId ? `reply-input-${parentId}` : `comment-input-${sig}`;
  const textarea = $(`#${inputId}`);
  const content = textarea.val().trim();

  if (!content) return;

  // Show loading state
  const submitBtn = $(event.target).find('button[type="submit"]');
  const originalText = submitBtn.html();
  submitBtn.prop('disabled', true).html('<i class="fa fa-spinner fa-spin"></i>');

  const formData = {
    'content': content,
    'csrfmiddlewaretoken': getCSRFToken()
  };

  if (parentId) {
    formData['parent_id'] = parentId;
  }

  $.ajax({
    type: "POST",
    url: `/logs/comment/add/${sig}/`,
    data: formData,
    success: function (response) {
      if (response.success) {
        // Clear input
        textarea.val('');

        // Hide reply form if it's a reply
        if (parentId) {
          cancelReply(parentId);
        }

        // Prepend comment to DOM
        prependComment(response, sig, parentId);

        // Update comment count
        updateCommentCount(sig, 1);
      }
    },
    error: function (xhr) {
      console.error('Error adding comment:', xhr.responseText);
      alert('Failed to add comment. Please try again.');
    },
    complete: function () {
      submitBtn.prop('disabled', false).html(originalText);
    }
  });
}

/**
 * Delete a comment
 */
function deleteComment(commentId, sig) {
  if (!confirm('Are you sure you want to delete this comment?')) return;

  $.ajax({
    type: "POST",
    url: `/logs/comment/delete/${commentId}/`,
    data: {
      'csrfmiddlewaretoken': getCSRFToken()
    },
    success: function (response) {
      if (response.success) {
        // Remove comment from DOM
        $(`#comment-${commentId}`).fadeOut(300, function () {
          $(this).remove();
        });

        // Update comment count (use deleted_count to account for nested replies)
        updateCommentCount(sig, -(response.deleted_count || 1));
      }
    },
    error: function (xhr) {
      if (xhr.status === 403) {
        alert('You are not authorized to delete this comment.');
      } else {
        alert('Failed to delete comment. Please try again.');
      }
    }
  });
}

/**
 * Show reply form for a comment
 */
function showReplyForm(commentId, sig, username = null) {
  // Hide all other reply forms
  $('.hidden[id^="reply-form-"]').addClass('hidden');

  // Show this reply form
  $(`#reply-form-${commentId}`).removeClass('hidden');
  const input = $(`#reply-input-${commentId}`);

  // Pre-fill username if provided (for nested replies)
  if (username) {
    input.val(`@${username} `);
  }

  input.focus();
}

/**
 * Cancel reply and hide form
 */
function cancelReply(commentId) {
  $(`#reply-form-${commentId}`).addClass('hidden');
  $(`#reply-input-${commentId}`).val('');
}

/**
 * Parse @mentions in text and convert to profile links
 * Matches the Django template filter pattern
 */
function parseMentions(text) {
  if (!text) return text;

  // Match @username patterns (alphanumeric, underscores, and dots)
  // This matches the pattern used in the Django template filter
  const pattern = /@([a-zA-Z0-9_.]+)/g;

  return text.replace(pattern, '<a href="/user-profile/$1/" class="text-blue-400 hover:text-blue-300 transition-colors font-semibold">@$1</a>');
}

/**
 * Prepend a new comment to the DOM
 */
function prependComment(commentData, sig, parentId) {
  // Determine styles based on whether it's a parent or reply
  const isReply = !!parentId;

  const containerClass = isReply
    ? 'ml-12 mt-3 relative group/reply'
    : 'mb-8 group/parent';

  const cardClass = isReply
    ? 'bg-transparent pl-0'
    : 'bg-[#161b22] border border-[#30363d] rounded-xl p-4 shadow-sm transition-colors';

  const avatarClass = isReply
    ? 'w-6 h-6 ring-1 ring-[#30363d]'
    : 'w-9 h-9 ring-2 ring-[#30363d]';

  const threadLines = isReply
    ? `<div class="absolute -left-6 top-0 bottom-0 w-0.5 bg-[#30363d] rounded-full group-hover/reply:bg-green-700 transition-colors duration-300"></div>
       <div class="absolute -left-6 top-4 w-4 h-0.5 bg-[#30363d] rounded-full group-hover/reply:bg-green-700 transition-colors duration-300"></div>`
    : '';

  const contentPadding = isReply ? 'pl-9' : 'mt-2';
  const actionsPadding = isReply ? 'pl-9' : '';
  const formPadding = isReply ? 'pl-9' : '';

  const commentHtml = `
    <div id="comment-${commentData.comment_id}" class="${containerClass}">
      
      ${threadLines}

      <div class="${cardClass} relative">
        <!-- Comment Header -->
        <div class="flex items-start justify-between mb-2">
          <div class="flex items-center gap-3">
            <img src="${commentData.user_image || '/static/assets/default-avatar.png'}" 
                 alt="${commentData.user}"
                 class="${avatarClass} rounded-full object-cover">
            <div class="flex flex-col leading-tight">
              <span class="text-sm font-semibold text-gray-200 hover:text-green-400 cursor-pointer transition-colors">${commentData.user}</span>
              <span class="text-[11px] text-gray-500">Just now</span>
            </div>
          </div>
          
          ${commentData.can_delete ? `
          <button onclick="deleteComment(${commentData.comment_id}, '${sig}')" 
                  class="text-gray-500 hover:text-red-400 transition-colors opacity-100 md:opacity-0 md:group-hover/parent:opacity-100 md:group-hover/reply:opacity-100 p-1">
            <i class="fa fa-trash text-xs"></i>
          </button>
          ` : ''}
        </div>

        <!-- Comment Content -->
        <div class="${contentPadding}">
          <p class="text-sm text-gray-300 whitespace-pre-wrap leading-relaxed">${parseMentions(commentData.content)}</p>
        </div>

        <!-- Comment Actions -->
        <div class="flex items-center gap-4 mt-3 ${actionsPadding}">
          <button onclick="showReplyForm(${commentData.comment_id}, '${sig}'${isReply ? `, '${commentData.user}'` : ''})" 
                  class="text-xs font-medium text-gray-500 hover:text-green-400 transition-colors flex items-center gap-1.5 py-1 px-2 -ml-2 rounded-md hover:bg-[#58a6ff]/10">
            <i class="fa fa-reply"></i>Reply
          </button>
        </div>

        <!-- Reply Form (Hidden by default) -->
        <div id="reply-form-${commentData.comment_id}" class="hidden mt-3 pt-3 border-t border-[#30363d]/30 ${formPadding}">
          <form onsubmit="addComment(event, '${sig}', ${commentData.comment_id}); return false;">
            <textarea 
              id="reply-input-${commentData.comment_id}"
              class="w-full bg-[#0d1117] border border-[#30363d] rounded-lg p-3 text-sm text-gray-300 focus:border-blue-500 focus:ring-1 focus:ring-blue-500 outline-none resize-none placeholder-gray-600"
              placeholder="Write a reply..."
              rows="2"
              maxlength="500"
              required></textarea>
            <div class="flex justify-end gap-2 mt-2">
              <button type="button" 
                      onclick="cancelReply(${commentData.comment_id})"
                      class="px-3 py-1.5 text-xs font-medium text-gray-400 hover:text-gray-300 transition-colors">
                Cancel
              </button>
              <button type="submit" 
                      class="px-3 py-1.5 bg-[#238636] hover:bg-[#2ea043] text-white text-xs font-medium rounded-md transition-colors shadow-sm border border-[rgba(240,246,252,0.1)]">
                Reply
              </button>
            </div>
          </form>
        </div>
      </div>
      <div id="replies-${commentData.comment_id}" class="space-y-1"></div>
    </div>
  `;

  if (parentId) {
    // Prepend to replies section
    $(`#replies-${parentId}`).prepend(commentHtml);
  } else {
    // Prepend to main comments list
    const commentsList = $(`#comments-list-${sig}`);
    // Remove "no comments" message if it exists
    commentsList.find('div.text-center').remove();
    commentsList.prepend(commentHtml);
  }
}

/**
 * Update comment count display
 */
function updateCommentCount(sig, delta) {
  const countElement = $(`#comment-count-${sig}`);
  const currentCount = parseInt(countElement.text()) || 0;
  const newCount = Math.max(0, currentCount + delta);
  countElement.text(newCount);
}

// Export comment functions
window.toggleComments = toggleComments;
window.addComment = addComment;
window.deleteComment = deleteComment;
window.showReplyForm = showReplyForm;
window.cancelReply = cancelReply;

/**
 * Quick follow/unfollow toggle for user from feed (for secondary network logs)
 */
function quickFollowUser(username, buttonElement) {
  const btn = $(buttonElement);

  // Prevent double-click
  if (btn.prop('disabled')) return;

  // Get current following state
  const isCurrentlyFollowing = btn.data('following') === 'true' || btn.data('following') === true;

  // Show loading state
  const originalText = btn.html();
  btn.prop('disabled', true).html('<i class="fa fa-spinner fa-spin"></i>');

  $.ajax({
    type: "POST",
    url: "/api/quick-follow/",
    contentType: "application/json",
    data: JSON.stringify({
      username: username
    }),
    headers: {
      "X-CSRFToken": getCSRFToken()
    },
    success: function (response) {
      if (response.status === "success") {
        // Update button based on new follow status
        if (response.is_following) {
          // Now following - update to "Following" state
          btn.html('<i class="fa fa-check"></i> Following')
            .removeClass('bg-[#238636] hover:bg-[#2ea043] border-[rgba(240,246,252,0.1)] shadow-sm')
            .addClass('bg-gray-700 text-gray-300 hover:bg-gray-600 border-gray-600')
            .data('following', 'true')
            .prop('disabled', false);
        } else {
          // Now not following - update to "Follow" state
          btn.html('Follow')
            .removeClass('bg-gray-700 text-gray-300 hover:bg-gray-600 border-gray-600')
            .addClass('bg-[#238636] text-white hover:bg-[#2ea043] border-[rgba(240,246,252,0.1)] shadow-sm')
            .data('following', 'false')
            .prop('disabled', false);
        }

        // Optional: Show success message in console
        console.log(response.message);
      }
    },
    error: function (xhr) {
      console.error('Error toggling follow:', xhr.responseText);

      // Restore button
      btn.html(originalText).prop('disabled', false);

      // Show error message
      let errorMsg = 'Failed to toggle follow status';
      if (xhr.responseJSON && xhr.responseJSON.message) {
        errorMsg = xhr.responseJSON.message;
      }

      // Visual feedback
      alert(errorMsg);
    }
  });
}

// Export quick follow function
window.quickFollowUser = quickFollowUser;
