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

function copyCurrentURL() {
    const currentURL = window.location.href;
    navigator.clipboard.writeText(currentURL)
        .then(() => {
            alert("🔗 Link copied successfully!");
        })
        .catch(err => {
            console.error("Failed to copy: ", err);
            alert("❌ Could not copy the link.");
        });
}

function copySnippet(sig) {
    const codeElement = document.getElementById(`code-snippet-${sig}`);
    const text = codeElement.innerText;
    navigator.clipboard.writeText(text).then(() => {
        alert('Snippet copied!');
    });
}


document.addEventListener('DOMContentLoaded', () => {
    const trigger = document.getElementById('exploreTrigger');
    const dropdown = document.getElementById('allExplore');

    if (trigger && dropdown) {
        trigger.addEventListener('click', (e) => {
            e.stopPropagation();
            dropdown.classList.toggle('hidden');
            dropdown.classList.toggle('flex');

            if (!dropdown.classList.contains('hidden')) {
                const closeOnOutside = (event) => {
                    if (!trigger.contains(event.target) && !dropdown.contains(event.target)) {
                        dropdown.classList.add('hidden');
                        dropdown.classList.remove('flex');
                        document.removeEventListener('click', closeOnOutside);
                    }
                };
                document.addEventListener('click', closeOnOutside);
            }
        });
    }
});


const openFilter = () => {
    if (window.screen.width < 1024) {
        const filterElement = document.getElementById('filterElement');
        const openFilterParent = document.getElementById('openFilterParent');
        filterElement.classList.toggle('fixed')
        filterElement.classList.add('flex')
        filterElement.classList.remove('hidden')
        openFilterParent.classList.remove('hidden')
    }
}

const closeFilter = () => {
    const filterElement = document.getElementById('filterElement');
    const openFilterParent = document.getElementById('openFilterParent');
    filterElement.classList.remove('fixed')
    filterElement.classList.add('hidden')
    openFilterParent.classList.add('hidden')
}

document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('.replyBtn').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            e.preventDefault();
            const target = document.querySelector(this.getAttribute('href'));
            if (target) {
                target.scrollIntoView({
                    behavior: 'smooth',
                    block: 
                    'center'
                });
                target.focus();
            }
        });
    });
});


const goTo = (url) => {
    window.open('https://' + url, '_blank');
}

const viewProfile = () => {
    const entireSection = document.getElementById('entireSection')
    const zoomProfile = document.getElementById('zoomProfile')
    entireSection.classList.toggle('blur')
    zoomProfile.classList.toggle('flex')
    zoomProfile.classList.toggle('hidden')
}

const closeProfile = () => {
    const entireSection = document.getElementById('entireSection')
    const zoomProfile = document.getElementById('zoomProfile')
    entireSection.classList.remove('blur')
    zoomProfile.classList.add('hidden')
    zoomProfile.classList.remove('flex')
}



//Toggle for follow or unfollow users
$(document).ready(function () {
    $(document).on('click', '.follow-btn', function() {
        let btn = $(this);
        let userId = btn.data("user-id");
        let actionUrl;
        let isFollowing = btn.find(".btn-text").text().trim().includes("Unfollow");

        if (isFollowing) {
            actionUrl = `/unfollow/${userId}/`;
        }else {
            actionUrl = `/follow/${userId}/`;   // URL for follow
        }

        $.ajax({
            url: actionUrl,
            type: "POST",
            headers: { "X-CSRFToken": getCSRFToken() },
            success: function (response) {
                if (response.status === "followed") {
                    btn.find(".btn-text").text("<Unfollow/>");
                    btn.removeClass("bg-[#6feb85] text-black");
                    btn.addClass("bg-[#262b34] text-white")
                    document.getElementById("clickSound").play();
                } 
                else if (response.status === "unfollowed") {
                    btn.find(".btn-text").text("<Follow/>");
                    btn.removeClass('bg-[#262b34] text-white')
                    btn.addClass("bg-[#6feb85] text-black")
                }

                $(`.followers-count`).text(`${response.followers_count}`);
                $(`.following-count`).text(`${response.following_count}`);
            },
            error: function (xhr) {
                console.error("Error:", xhr.responseText);
            }
        });
    });
}); 


// For toasting
function toast(message = "Something happened!", type = "default", duration = 3000) {
    const container = document.getElementById("toast-container");
    if (!container) return;

    const toast = document.createElement("div");

    // Type-based color classes
    let color = "bg-gray-800 text-white";
    if (type === "success") color = "bg-green-600 text-white";
    if (type === "error") color = "bg-red-600 text-white";
    if (type === "warn") color = "bg-yellow-400 text-black";

    // Apply base Tailwind styling and custom entry class
    toast.className = `
        px-4 py-2 rounded-md shadow-lg font-mono text-sm
        ${color} toast-animate-in
    `;

    toast.innerText = message;
    container.appendChild(toast);

    // Add exit animation before removal
    setTimeout(() => {
        toast.classList.remove("toast-animate-in");
        toast.classList.add("toast-animate-out");
    }, duration);

    setTimeout(() => {
        toast.remove();
    }, duration + 600);
}

//for reward + emoji drop
function triggerDevmateReward(message, emojis) {
    const defaultEmojis = ["🎉", "✨", "🔥", "🚀", "🏆", "🥳"];
    if (!emojis || emojis.length === 0) {
        emojis = defaultEmojis;
    }

    const banner = document.getElementById('devmate-reward-banner');
    const messageSpan = document.getElementById('devmate-reward-message');
    const emojiContainer = document.getElementById('emoji-drop-container');

    messageSpan.textContent = message;
    banner.classList.remove('hidden');
    banner.classList.add('devmate-reward-anim-show');

    // Drop Emojis
    for (let i = 0; i < 60; i++) {
        const emoji = document.createElement('div');
        emoji.classList.add('emoji-drop');
        emoji.style.left = Math.random() * 100 + "vw";
        emoji.style.animationDuration = (2 + Math.random()) + "s";
        emoji.innerText = emojis[Math.floor(Math.random() * emojis.length)];
        emojiContainer.appendChild(emoji);

        setTimeout(() => emoji.remove(), 4000);
    }

    // Auto-hide banner
    setTimeout(() => {
        banner.classList.remove('devmate-reward-anim-show');
        setTimeout(() => banner.classList.add('hidden'), 500);
    }, 6000);
}