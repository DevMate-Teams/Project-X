/**
 * @mention Autocomplete System
 * Provides real-time username suggestions when typing @ in text inputs
 */

class MentionAutocomplete {
    constructor(options = {}) {
        this.apiUrl = options.apiUrl || '/logs/api/users/search/';
        this.minChars = options.minChars || 1;
        this.debounceTime = options.debounceTime || 200;
        this.maxSuggestions = options.maxSuggestions || 10;
        
        this.activeInput = null;
        this.dropdown = null;
        this.selectedIndex = -1;
        this.suggestions = [];
        this.mentionStart = -1;
        this.debounceTimer = null;
        
        this.init();
    }
    
    init() {
        // Create the dropdown element
        this.createDropdown();
        
        // Attach event listeners using event delegation
        document.addEventListener('input', this.handleInput.bind(this));
        document.addEventListener('keydown', this.handleKeydown.bind(this));
        document.addEventListener('click', this.handleClickOutside.bind(this));
        
        // Handle focus events for textareas and inputs
        document.addEventListener('focusin', this.handleFocus.bind(this));
        document.addEventListener('focusout', this.handleBlur.bind(this));
    }
    
    createDropdown() {
        this.dropdown = document.createElement('div');
        this.dropdown.className = 'mention-dropdown hidden';
        this.dropdown.innerHTML = '';
        document.body.appendChild(this.dropdown);
        
        // Styles are now defined in input.css
        // No need to add them dynamically
    }
    
    handleFocus(e) {
        const target = e.target;
        if (this.isValidInput(target)) {
            this.activeInput = target;
        }
    }
    
    handleBlur(e) {
        // Delay hiding to allow click on dropdown
        setTimeout(() => {
            if (!this.dropdown.contains(document.activeElement)) {
                this.hideDropdown();
            }
        }, 150);
    }
    
    isValidInput(element) {
        // Check if the element is a valid text input for mentions
        if (!element) return false;
        
        const tagName = element.tagName.toLowerCase();
        const validTags = ['input', 'textarea'];
        
        if (!validTags.includes(tagName)) return false;
        
        // For input elements, only allow text type
        if (tagName === 'input') {
            const inputType = element.type?.toLowerCase() || 'text';
            return ['text', 'search'].includes(inputType);
        }
        
        return true;
    }
    
    handleInput(e) {
        const target = e.target;
        
        if (!this.isValidInput(target)) return;
        
        this.activeInput = target;
        
        // Clear previous debounce
        if (this.debounceTimer) {
            clearTimeout(this.debounceTimer);
        }
        
        const cursorPos = target.selectionStart;
        const text = target.value;
        
        // Find if we're in a mention context
        const mentionMatch = this.findMentionContext(text, cursorPos);
        
        if (mentionMatch) {
            this.mentionStart = mentionMatch.start;
            const query = mentionMatch.query;
            
            if (query.length >= this.minChars) {
                this.debounceTimer = setTimeout(() => {
                    this.fetchSuggestions(query);
                }, this.debounceTime);
            } else if (query.length === 0) {
                // Show dropdown immediately when @ is typed
                this.debounceTimer = setTimeout(() => {
                    this.fetchSuggestions('');
                }, this.debounceTime);
            }
        } else {
            this.hideDropdown();
        }
    }
    
    findMentionContext(text, cursorPos) {
        // Look backwards from cursor to find @
        let start = cursorPos - 1;
        
        while (start >= 0) {
            const char = text[start];
            
            if (char === '@') {
                // Found @, check if it's a valid mention start
                // Should be at beginning or after whitespace/newline
                if (start === 0 || /[\s\n]/.test(text[start - 1])) {
                    const query = text.substring(start + 1, cursorPos);
                    // Check if query contains only valid username characters
                    if (/^[a-zA-Z0-9_.]*$/.test(query)) {
                        return { start, query };
                    }
                }
                return null;
            }
            
            // If we hit whitespace or newline, no mention context
            if (/[\s\n]/.test(char)) {
                return null;
            }
            
            // If character is not valid for username, no mention
            if (!/[a-zA-Z0-9_.]/.test(char)) {
                return null;
            }
            
            start--;
        }
        
        return null;
    }
    
    async fetchSuggestions(query) {
        this.showLoading();
        
        try {
            const response = await fetch(`${this.apiUrl}?q=${encodeURIComponent(query)}`);
            const data = await response.json();
            
            this.suggestions = data.users || [];
            this.selectedIndex = -1;
            this.renderSuggestions();
        } catch (error) {
            console.error('Error fetching mention suggestions:', error);
            this.hideDropdown();
        }
    }
    
    showLoading() {
        this.dropdown.innerHTML = '<div class="mention-loading"><i class="fa fa-spinner fa-spin"></i> Loading...</div>';
        this.positionDropdown();
        this.dropdown.classList.remove('hidden');
    }
    
    renderSuggestions() {
        if (this.suggestions.length === 0) {
            this.dropdown.innerHTML = '<div class="mention-no-results">No users found</div>';
        } else {
            this.dropdown.innerHTML = this.suggestions.map((user, index) => `
                <div class="mention-dropdown-item ${index === this.selectedIndex ? 'selected' : ''}" 
                     data-index="${index}" 
                     data-username="${user.username}">
                    <img src="${user.profile_image}" alt="${user.username}" class="mention-avatar" onerror="this.src='/static/assets/default-avatar.png'">
                    <div class="mention-user-info">
                        <div class="mention-username">
                            <span class="at-symbol">@</span>${user.username}
                            ${user.is_following ? '<span class="mention-following-badge">Following</span>' : ''}
                        </div>
                        <div class="mention-fullname">${user.full_name}</div>
                    </div>
                </div>
            `).join('');
            
            // Add click handlers to items
            this.dropdown.querySelectorAll('.mention-dropdown-item').forEach(item => {
                item.addEventListener('mousedown', (e) => {
                    e.preventDefault();
                    const username = item.dataset.username;
                    this.selectSuggestion(username);
                });
                
                item.addEventListener('mouseenter', () => {
                    this.selectedIndex = parseInt(item.dataset.index);
                    this.updateSelection();
                });
            });
        }
        
        this.positionDropdown();
        this.dropdown.classList.remove('hidden');
    }
    
    positionDropdown() {
        if (!this.activeInput) return;
        
        const rect = this.activeInput.getBoundingClientRect();
        const scrollTop = window.pageYOffset || document.documentElement.scrollTop;
        const scrollLeft = window.pageXOffset || document.documentElement.scrollLeft;
        
        // Position below the input
        let top = rect.bottom + scrollTop + 4;
        let left = rect.left + scrollLeft;
        
        // Check if dropdown would go off screen
        const dropdownRect = this.dropdown.getBoundingClientRect();
        const viewportHeight = window.innerHeight;
        
        // If it would go below viewport, position above
        if (rect.bottom + dropdownRect.height > viewportHeight) {
            top = rect.top + scrollTop - dropdownRect.height - 4;
        }
        
        // Ensure it doesn't go off the right edge
        const viewportWidth = window.innerWidth;
        if (left + dropdownRect.width > viewportWidth) {
            left = viewportWidth - dropdownRect.width - 10;
        }
        
        this.dropdown.style.top = `${top}px`;
        this.dropdown.style.left = `${left}px`;
    }
    
    handleKeydown(e) {
        if (this.dropdown.classList.contains('hidden')) return;
        
        switch (e.key) {
            case 'ArrowDown':
                e.preventDefault();
                this.selectedIndex = Math.min(this.selectedIndex + 1, this.suggestions.length - 1);
                this.updateSelection();
                break;
                
            case 'ArrowUp':
                e.preventDefault();
                this.selectedIndex = Math.max(this.selectedIndex - 1, 0);
                this.updateSelection();
                break;
                
            case 'Enter':
            case 'Tab':
                if (this.selectedIndex >= 0 && this.suggestions[this.selectedIndex]) {
                    e.preventDefault();
                    this.selectSuggestion(this.suggestions[this.selectedIndex].username);
                }
                break;
                
            case 'Escape':
                this.hideDropdown();
                break;
        }
    }
    
    updateSelection() {
        this.dropdown.querySelectorAll('.mention-dropdown-item').forEach((item, index) => {
            item.classList.toggle('selected', index === this.selectedIndex);
        });
        
        // Scroll selected item into view
        const selectedItem = this.dropdown.querySelector('.mention-dropdown-item.selected');
        if (selectedItem) {
            selectedItem.scrollIntoView({ block: 'nearest' });
        }
    }
    
    selectSuggestion(username) {
        if (!this.activeInput || this.mentionStart === -1) return;
        
        const text = this.activeInput.value;
        const cursorPos = this.activeInput.selectionStart;
        
        // Replace the @query with @username
        const beforeMention = text.substring(0, this.mentionStart);
        const afterMention = text.substring(cursorPos);
        
        const newText = `${beforeMention}@${username} ${afterMention}`;
        this.activeInput.value = newText;
        
        // Set cursor position after the inserted mention
        const newCursorPos = this.mentionStart + username.length + 2; // +2 for @ and space
        this.activeInput.setSelectionRange(newCursorPos, newCursorPos);
        
        // Trigger input event for any listeners
        this.activeInput.dispatchEvent(new Event('input', { bubbles: true }));
        
        this.hideDropdown();
        this.activeInput.focus();
    }
    
    handleClickOutside(e) {
        if (!this.dropdown.contains(e.target) && e.target !== this.activeInput) {
            this.hideDropdown();
        }
    }
    
    hideDropdown() {
        this.dropdown.classList.add('hidden');
        this.selectedIndex = -1;
        this.mentionStart = -1;
    }
}

// Initialize the mention autocomplete when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    // Only initialize if user is logged in (check for CSRF token as indicator)
    if (document.querySelector('[name=csrfmiddlewaretoken]') || document.cookie.includes('csrftoken')) {
        window.mentionAutocomplete = new MentionAutocomplete();
    }
});

// Export for module usage
if (typeof module !== 'undefined' && module.exports) {
    module.exports = MentionAutocomplete;
}
