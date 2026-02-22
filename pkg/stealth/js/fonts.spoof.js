// Font Enumeration Spoof
// Normalizes the font fingerprint by returning a curated list of ~40 common fonts
// regardless of what's actually installed on the system.

(function () {
    'use strict';

    // Common fonts found on most systems — using these normalizes the fingerprint
    const commonFonts = [
        'Arial', 'Arial Black', 'Arial Narrow', 'Calibri', 'Cambria',
        'Cambria Math', 'Comic Sans MS', 'Consolas', 'Constantia', 'Corbel',
        'Courier', 'Courier New', 'Georgia', 'Helvetica', 'Helvetica Neue',
        'Impact', 'Lucida Console', 'Lucida Sans Unicode', 'Microsoft Sans Serif',
        'MS Gothic', 'MS PGothic', 'MS Sans Serif', 'MS Serif', 'Palatino Linotype',
        'Segoe Print', 'Segoe Script', 'Segoe UI', 'Segoe UI Light',
        'Segoe UI Semibold', 'Segoe UI Symbol', 'Tahoma', 'Times',
        'Times New Roman', 'Trebuchet MS', 'Verdana', 'Wingdings',
        'Wingdings 2', 'Wingdings 3', 'Symbol', 'Webdings'
    ];

    const commonFontsSet = new Set(commonFonts.map(f => f.toLowerCase()));

    // Override document.fonts.check to return true only for common fonts
    if (document.fonts && document.fonts.check) {
        const originalCheck = document.fonts.check.bind(document.fonts);

        document.fonts.check = function (fontSpec, text) {
            // Parse font family from the spec (e.g., "12px Arial" → "Arial")
            const parts = fontSpec.split(/\s+/);
            // Font family is usually the last part(s)
            let family = parts.slice(1).join(' ').replace(/['"]/g, '').trim();
            if (!family) family = parts[0];

            // Only return true for common fonts
            if (commonFontsSet.has(family.toLowerCase())) {
                return true;
            }

            // For uncommon fonts, return false to normalize fingerprint
            return false;
        };
    }

    // Spoof font enumeration via FontFaceSet.forEach if available  
    if (document.fonts && typeof document.fonts.forEach === 'function') {
        const originalForEach = document.fonts.forEach.bind(document.fonts);

        document.fonts.forEach = function (callback, thisArg) {
            // Only iterate over common fonts that actually exist
            originalForEach(function (fontFace) {
                if (commonFontsSet.has(fontFace.family.toLowerCase().replace(/['"]/g, ''))) {
                    callback.call(thisArg, fontFace);
                }
            });
        };
    }

    // Override the offsetWidth/offsetHeight trick for font detection
    // Many fingerprinters create a span, set font-family, and measure dimensions
    // We add tiny random variation to prevent consistent measurements
    const originalOffsetWidth = Object.getOwnPropertyDescriptor(HTMLElement.prototype, 'offsetWidth');
    const originalOffsetHeight = Object.getOwnPropertyDescriptor(HTMLElement.prototype, 'offsetHeight');

    if (originalOffsetWidth && originalOffsetWidth.get) {
        Object.defineProperty(HTMLElement.prototype, 'offsetWidth', {
            get: function () {
                const width = originalOffsetWidth.get.call(this);
                // Only add noise to elements likely used for font detection
                // (small invisible elements with specific font-family)
                if (this.style && this.style.position === 'absolute' &&
                    this.style.left === '-9999px') {
                    return width + (Math.random() > 0.5 ? 1 : 0);
                }
                return width;
            }
        });
    }
})();
