// Canvas Fingerprint Noise Injection
// Adds imperceptible random noise to canvas operations to defeat canvas fingerprinting.
// This makes each session produce a slightly different canvas hash.

(function () {
    'use strict';

    // Save originals
    const originalToDataURL = HTMLCanvasElement.prototype.toDataURL;
    const originalToBlob = HTMLCanvasElement.prototype.toBlob;
    const originalGetImageData = CanvasRenderingContext2D.prototype.getImageData;

    // Seed for consistent noise within a session but different across sessions
    const noiseSeed = Math.floor(Math.random() * 1000);

    function addNoise(data) {
        // Add very small noise (±1-2 to random channels of random pixels)
        // Imperceptible to humans but changes the hash
        const len = data.length;
        const noiseCount = Math.max(10, Math.floor(len / 1000)); // ~0.1% of pixels

        for (let i = 0; i < noiseCount; i++) {
            const idx = (Math.floor(Math.random() * (len / 4)) * 4); // Align to pixel boundary
            const channel = Math.floor(Math.random() * 3); // R, G, or B (skip alpha)
            const noise = Math.random() > 0.5 ? 1 : -1;
            const val = data[idx + channel];
            data[idx + channel] = Math.max(0, Math.min(255, val + noise));
        }
        return data;
    }

    // Override toDataURL
    HTMLCanvasElement.prototype.toDataURL = function () {
        const ctx = this.getContext('2d');
        if (ctx) {
            try {
                const imageData = originalGetImageData.call(ctx, 0, 0, this.width, this.height);
                addNoise(imageData.data);
                ctx.putImageData(imageData, 0, 0);
            } catch (e) {
                // CORS or other error — skip noise injection
            }
        }
        return originalToDataURL.apply(this, arguments);
    };

    // Override toBlob
    HTMLCanvasElement.prototype.toBlob = function () {
        const ctx = this.getContext('2d');
        if (ctx) {
            try {
                const imageData = originalGetImageData.call(ctx, 0, 0, this.width, this.height);
                addNoise(imageData.data);
                ctx.putImageData(imageData, 0, 0);
            } catch (e) {
                // CORS or other error — skip noise injection
            }
        }
        return originalToBlob.apply(this, arguments);
    };

    // Override getImageData
    CanvasRenderingContext2D.prototype.getImageData = function () {
        const imageData = originalGetImageData.apply(this, arguments);
        try {
            addNoise(imageData.data);
        } catch (e) { }
        return imageData;
    };
})();
