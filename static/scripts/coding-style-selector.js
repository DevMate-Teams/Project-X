// Coding Style Selector Modal
let codingStyles = [];
let currentStyleId = null;

// Open modal and load styles
async function openCodingStyleModal() {
    try {
        const response = await fetch('/coding-style/get/');
        const data = await response.json();

        codingStyles = data.styles;
        currentStyleId = data.current_style_id;

        renderCodingStyles();
        document.getElementById('coding-style-modal').classList.remove('hidden');
        document.body.style.overflow = 'hidden';

        // Show first style by default or current style if exists
        if (codingStyles.length > 0) {
            const styleToShow = currentStyleId
                ? codingStyles.find(s => s.id === currentStyleId) || codingStyles[0]
                : codingStyles[0];
            showStyleDetails(styleToShow);
        }
    } catch (error) {
        console.error('Error loading coding styles:', error);
    }
}

// Close modal
function closeCodingStyleModal() {
    document.getElementById('coding-style-modal').classList.add('hidden');
    document.body.style.overflow = '';
}

// Render styles grid
function renderCodingStyles() {
    const grid = document.getElementById('styles-grid');
    grid.innerHTML = codingStyles.map(style => `
        <div onclick="showStyleDetails(${JSON.stringify(style).replace(/"/g, '&quot;')})" 
             class="relative cursor-pointer p-4 rounded-lg border border-[#30363d] hover:border-[#8b949e] transition-all duration-200 bg-[#161b22] hover:bg-[#1c2128] ${style.id === currentStyleId ? 'border-[#238636] ring-1 ring-[#238636]/50 bg-[#238636]/5' : ''}">
            ${style.id === currentStyleId ? '<div class="absolute top-2 right-2 px-2 py-0.5 bg-[#238636]/20 text-[#2ea043] border border-[#238636]/50 text-xs font-semibold rounded-full">Current</div>' : ''}
            <div class="flex items-center justify-center mb-3">
                <img src="/static/assets/coding-style-logo/${style.logo}" alt="${style.name}" class="w-12 h-12 object-contain">
            </div>
            <h3 class="text-sm font-semibold text-[#c9d1d9] mb-1">${style.name}</h3>
            <p class="text-xs text-[#8b949e] line-clamp-2">${style.description.split('\n')[0]}</p>
        </div>
    `).join('');
}

// Show style details in preview panel
function showStyleDetails(style) {
    document.getElementById('detail-logo').src = `/static/assets/coding-style-logo/${style.logo}`;
    document.getElementById('detail-name').textContent = style.name;
    document.getElementById('detail-description').textContent = style.description;
    document.getElementById('select-style-btn').setAttribute('data-style-id', style.id);

    // Highlight selected card visually (optional, as we rebuild grid on selection usually, but good for immediate feedback)
    // For now, the grid render handles the 'current' style border. 
    // If we want to highlight the *previewed* style, we could add a class here.
}

// Select and save style
async function selectCodingStyle() {
    const styleId = document.getElementById('select-style-btn').getAttribute('data-style-id');
    const btn = document.getElementById('select-style-btn');

    if (!styleId) return;

    btn.disabled = true;
    btn.innerHTML = '<i class="fa fa-spinner fa-spin mr-2"></i>Saving...';

    try {
        const formData = new FormData();
        formData.append('style_id', styleId);
        // Get CSRF token from the page
        const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')
            ? document.querySelector('[name=csrfmiddlewaretoken]').value
            : getCookie('csrftoken');

        formData.append('csrfmiddlewaretoken', csrfToken);

        const response = await fetch('/coding-style/update/', {
            method: 'POST',
            body: formData,
            headers: {
                'X-CSRFToken': csrfToken
            }
        });

        const data = await response.json();

        if (data.success) {
            // Update UI
            const badge = document.getElementById('coding-style-badge');
            if (badge) {
                // Update badge content and style
                badge.className = "text-sm px-3 py-2 w-fit rounded-lg bg-[#262b34] text-white shadow-sm border border-[#333] flex items-center gap-2";
                badge.innerHTML = `<img src="/static/assets/coding-style-logo/${data.style.logo}" alt="${data.style.name}" class="w-5 h-5">${data.style.name}`;
            }

            currentStyleId = data.style.id;
            closeCodingStyleModal();
        } else {
            alert('Error: ' + data.error);
        }
    } catch (error) {
        console.error('Error saving coding style:', error);
        alert('Failed to save coding style');
    } finally {
        btn.disabled = false;
        btn.innerHTML = '<i class="fa fa-check mr-2"></i>Select This Style';
    }
}

// Helper to get cookie (standard Django)
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

// Close on escape key
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        closeCodingStyleModal();
    }
});
