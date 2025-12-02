/**
 * Syntax Highlighting System for Code Snippets
 * Uses highlight.js with automatic language detection
 * Supports GitHub-style dark theme
 */

class SyntaxHighlighter {
    constructor() {
        this.initialized = false;
        this.highlightedElements = new Set();
        this.init();
    }

    init() {
        // Wait for highlight.js to load
        if (typeof hljs === 'undefined') {
            // Retry after a short delay if hljs not yet loaded
            setTimeout(() => this.init(), 100);
            return;
        }

        // Configure highlight.js
        hljs.configure({
            ignoreUnescapedHTML: true,
            throwUnescapedHTML: false,
            languages: [
                'javascript', 'typescript', 'python', 'java', 'c', 'cpp', 'csharp',
                'go', 'rust', 'ruby', 'php', 'swift', 'kotlin', 'scala',
                'html', 'css', 'scss', 'json', 'xml', 'yaml', 'markdown',
                'sql', 'bash', 'shell', 'powershell',
                'dockerfile', 'nginx', 'apache',
                'plaintext'
            ]
        });

        this.initialized = true;

        // Initial highlighting
        this.highlightAll();

        // Set up MutationObserver for dynamically added content
        this.observeDynamicContent();
    }

    /**
     * Highlight all code snippets on the page
     */
    highlightAll() {
        if (!this.initialized) return;

        // Find all code snippet containers
        const codeBlocks = document.querySelectorAll('pre[id^="code-snippet-"] code');
        
        codeBlocks.forEach(block => {
            this.highlightElement(block);
        });
    }

    /**
     * Highlight a single code element
     */
    highlightElement(element) {
        if (!element || this.highlightedElements.has(element)) return;

        // Get the code content
        const code = element.textContent || element.innerText;
        if (!code.trim()) return;

        // Detect the language
        const detectedLang = this.detectLanguage(code);
        
        // Apply highlighting
        try {
            if (detectedLang && detectedLang !== 'plaintext') {
                const result = hljs.highlight(code, { language: detectedLang });
                element.innerHTML = result.value;
                element.classList.add('hljs', `language-${detectedLang}`);
            } else {
                // Try auto-detection
                const result = hljs.highlightAuto(code);
                element.innerHTML = result.value;
                element.classList.add('hljs');
                if (result.language) {
                    element.classList.add(`language-${result.language}`);
                }
            }

            // Mark as highlighted
            this.highlightedElements.add(element);

            // Update the language badge if present
            this.updateLanguageBadge(element, detectedLang || 'auto');

        } catch (error) {
            console.warn('Syntax highlighting failed:', error);
        }
    }

    /**
     * Detect programming language from code content
     * Uses heuristics for better accuracy before falling back to hljs auto-detection
     */
    detectLanguage(code) {
        const trimmedCode = code.trim();
        
        // Python indicators
        if (/^(import |from .+ import |def |class |if __name__|@\w+|print\(|async def )/.test(trimmedCode) ||
            /:\s*$/.test(trimmedCode.split('\n')[0]) && !/[{;]/.test(trimmedCode.split('\n')[0])) {
            return 'python';
        }

        // JavaScript/TypeScript indicators
        if (/^(const |let |var |function |import |export |async |await |=>\s*{|class .+ extends)/.test(trimmedCode) ||
            /\.(then|catch|finally)\(/.test(trimmedCode) ||
            /console\.(log|error|warn)/.test(trimmedCode)) {
            // Check for TypeScript specific syntax
            if (/:\s*(string|number|boolean|any|void|never|unknown)\b/.test(trimmedCode) ||
                /interface\s+\w+|type\s+\w+\s*=|<\w+>/.test(trimmedCode)) {
                return 'typescript';
            }
            return 'javascript';
        }

        // Java indicators
        if (/^(public |private |protected |package |import java\.|class \w+ (extends|implements))/.test(trimmedCode) ||
            /System\.(out|err)\.print/.test(trimmedCode) ||
            /public static void main/.test(trimmedCode)) {
            return 'java';
        }

        // C/C++ indicators
        if (/^#include\s*[<"]/.test(trimmedCode) ||
            /^(int|void|char|float|double)\s+main\s*\(/.test(trimmedCode) ||
            /printf\(|scanf\(|cout\s*<<|cin\s*>>/.test(trimmedCode)) {
            if (/cout|cin|std::|nullptr|class\s+\w+\s*{|template\s*</.test(trimmedCode)) {
                return 'cpp';
            }
            return 'c';
        }

        // C# indicators
        if (/^using\s+System;|namespace\s+\w+|Console\.(Write|Read)/.test(trimmedCode) ||
            /public\s+(class|interface|struct|enum)\s+\w+/.test(trimmedCode)) {
            return 'csharp';
        }

        // Go indicators
        if (/^package\s+\w+|^import\s+\(|func\s+\w+\(|fmt\.(Print|Scan)/.test(trimmedCode) ||
            /:=/.test(trimmedCode)) {
            return 'go';
        }

        // Rust indicators
        if (/^(use\s+\w+|fn\s+\w+|let\s+mut|impl\s+\w+|struct\s+\w+|enum\s+\w+|pub\s+fn)/.test(trimmedCode) ||
            /println!\(|vec!\[|&str|&mut/.test(trimmedCode)) {
            return 'rust';
        }

        // Ruby indicators
        if (/^(require|gem|def\s+\w+|class\s+\w+\s*<|module\s+\w+|end$)/.test(trimmedCode) ||
            /puts\s|\.each\s+do|do\s*\|/.test(trimmedCode)) {
            return 'ruby';
        }

        // PHP indicators
        if (/^<\?php|\$\w+\s*=|function\s+\w+\s*\(.*\)\s*{|echo\s|->/.test(trimmedCode)) {
            return 'php';
        }

        // Swift indicators
        if (/^import\s+(Foundation|UIKit|SwiftUI)|func\s+\w+\s*\(|var\s+\w+:\s*\w+|let\s+\w+:\s*\w+/.test(trimmedCode) ||
            /print\(|guard\s+let|if\s+let/.test(trimmedCode)) {
            return 'swift';
        }

        // Kotlin indicators
        if (/^(package|import)\s+[\w.]+|fun\s+\w+|val\s+\w+|var\s+\w+|println\(/.test(trimmedCode) ||
            /:\s*(Int|String|Boolean|Double|Float)\b/.test(trimmedCode)) {
            return 'kotlin';
        }

        // HTML indicators
        if (/^<!DOCTYPE|^<html|^<head|^<body|<div|<span|<p>|<a\s|<img\s|<script|<style|<\/\w+>/.test(trimmedCode)) {
            return 'html';
        }

        // CSS/SCSS indicators
        if (/^[\.\#\w\-\[\]]+\s*{|@media|@import|@keyframes|:root\s*{/.test(trimmedCode)) {
            if (/@mixin|@include|\$\w+:|@extend/.test(trimmedCode)) {
                return 'scss';
            }
            return 'css';
        }

        // JSON indicators
        if (/^\s*[\[{]/.test(trimmedCode) && /[\]}]\s*$/.test(trimmedCode) &&
            /"[\w]+"\s*:/.test(trimmedCode)) {
            return 'json';
        }

        // YAML indicators
        if (/^\w+:\s*(\n|$)|^-\s+\w+:/.test(trimmedCode) && !/[{};]/.test(trimmedCode)) {
            return 'yaml';
        }

        // SQL indicators
        if (/^(SELECT|INSERT|UPDATE|DELETE|CREATE|ALTER|DROP|FROM|WHERE|JOIN)\s/i.test(trimmedCode)) {
            return 'sql';
        }

        // Bash/Shell indicators
        if (/^#!/.test(trimmedCode) || /^\$\s|^echo\s|^cd\s|^ls\s|^grep\s|^awk\s|^sed\s|\|\s*(grep|awk|sed)/.test(trimmedCode)) {
            return 'bash';
        }

        // Dockerfile indicators
        if (/^(FROM|RUN|CMD|EXPOSE|ENV|ADD|COPY|ENTRYPOINT|VOLUME|WORKDIR)\s/m.test(trimmedCode)) {
            return 'dockerfile';
        }

        // Markdown indicators
        if (/^#+\s|^\*\*\w|\*\w\*|^\-\s\[|```/.test(trimmedCode)) {
            return 'markdown';
        }

        // Let hljs auto-detect
        return null;
    }

    /**
     * Update the language badge in the code block header
     */
    updateLanguageBadge(codeElement, language) {
        const container = codeElement.closest('.relative');
        if (!container) return;

        const badge = container.querySelector('.code-lang-badge');
        if (badge) {
            badge.textContent = this.getLanguageDisplayName(language);
            badge.classList.remove('hidden');
        }
    }

    /**
     * Get display name for a language
     */
    getLanguageDisplayName(lang) {
        const displayNames = {
            'javascript': 'JavaScript',
            'typescript': 'TypeScript',
            'python': 'Python',
            'java': 'Java',
            'c': 'C',
            'cpp': 'C++',
            'csharp': 'C#',
            'go': 'Go',
            'rust': 'Rust',
            'ruby': 'Ruby',
            'php': 'PHP',
            'swift': 'Swift',
            'kotlin': 'Kotlin',
            'scala': 'Scala',
            'html': 'HTML',
            'css': 'CSS',
            'scss': 'SCSS',
            'json': 'JSON',
            'xml': 'XML',
            'yaml': 'YAML',
            'markdown': 'Markdown',
            'sql': 'SQL',
            'bash': 'Bash',
            'shell': 'Shell',
            'powershell': 'PowerShell',
            'dockerfile': 'Dockerfile',
            'nginx': 'Nginx',
            'plaintext': 'Plain Text',
            'auto': 'Code'
        };
        return displayNames[lang] || lang.charAt(0).toUpperCase() + lang.slice(1);
    }

    /**
     * Observe DOM for dynamically added code snippets
     */
    observeDynamicContent() {
        const observer = new MutationObserver((mutations) => {
            mutations.forEach((mutation) => {
                mutation.addedNodes.forEach((node) => {
                    if (node.nodeType === Node.ELEMENT_NODE) {
                        // Check if the added node contains code snippets
                        const codeBlocks = node.querySelectorAll ? 
                            node.querySelectorAll('pre[id^="code-snippet-"] code') : [];
                        codeBlocks.forEach(block => this.highlightElement(block));

                        // Check if the node itself is a code block
                        if (node.matches && node.matches('pre[id^="code-snippet-"] code')) {
                            this.highlightElement(node);
                        }
                    }
                });
            });
        });

        observer.observe(document.body, {
            childList: true,
            subtree: true
        });
    }

    /**
     * Manually highlight a specific code block by signature
     */
    highlightBySignature(sig) {
        const element = document.querySelector(`#code-snippet-${sig} code`);
        if (element) {
            // Remove from highlighted set to allow re-highlighting
            this.highlightedElements.delete(element);
            this.highlightElement(element);
        }
    }
}

// Initialize syntax highlighter when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    window.syntaxHighlighter = new SyntaxHighlighter();
});

// Re-highlight when new content is loaded via AJAX
$(document).ajaxComplete(function() {
    if (window.syntaxHighlighter) {
        setTimeout(() => window.syntaxHighlighter.highlightAll(), 100);
    }
});

// Export for module usage
if (typeof module !== 'undefined' && module.exports) {
    module.exports = SyntaxHighlighter;
}
