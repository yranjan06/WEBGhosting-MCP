// WebGL Fingerprint Noise Injection
// Injects noise into WebGL readPixels and spoofs renderer/vendor strings.
// Works in conjunction with the main webgl.vendor.js for comprehensive WebGL stealth.

(function () {
    'use strict';

    // Override readPixels to add subtle noise
    const originalReadPixels = WebGLRenderingContext.prototype.readPixels;
    const originalReadPixels2 = WebGL2RenderingContext && WebGL2RenderingContext.prototype.readPixels;

    function addNoiseToPixels(pixels) {
        if (!pixels || !pixels.length) return;

        // Add noise to ~0.05% of pixel values
        const noiseCount = Math.max(5, Math.floor(pixels.length / 2000));
        for (let i = 0; i < noiseCount; i++) {
            const idx = Math.floor(Math.random() * pixels.length);
            const noise = Math.random() > 0.5 ? 1 : -1;
            pixels[idx] = Math.max(0, Math.min(255, pixels[idx] + noise));
        }
    }

    WebGLRenderingContext.prototype.readPixels = function () {
        originalReadPixels.apply(this, arguments);
        // The pixel data is in the last argument (ArrayBufferView)
        const pixels = arguments[arguments.length - 1];
        if (pixels && pixels.length) {
            addNoiseToPixels(pixels);
        }
    };

    if (WebGL2RenderingContext && originalReadPixels2) {
        WebGL2RenderingContext.prototype.readPixels = function () {
            originalReadPixels2.apply(this, arguments);
            const pixels = arguments[arguments.length - 1];
            if (pixels && pixels.length) {
                addNoiseToPixels(pixels);
            }
        };
    }

    // Override getParameter for additional renderer info randomization
    const originalGetParam = WebGLRenderingContext.prototype.getParameter;
    const originalGetParam2 = WebGL2RenderingContext && WebGL2RenderingContext.prototype.getParameter;

    const UNMASKED_VENDOR = 0x9245; // UNMASKED_VENDOR_WEBGL
    const UNMASKED_RENDERER = 0x9246; // UNMASKED_RENDERER_WEBGL

    function patchGetParameter(original) {
        return function (param) {
            if (param === UNMASKED_VENDOR) {
                return opts.webgl_vendor || 'Intel Inc.';
            }
            if (param === UNMASKED_RENDERER) {
                return opts.webgl_renderer || 'Intel Iris OpenGL Engine';
            }
            return original.apply(this, arguments);
        };
    }

    WebGLRenderingContext.prototype.getParameter = patchGetParameter(originalGetParam);

    if (WebGL2RenderingContext && originalGetParam2) {
        WebGL2RenderingContext.prototype.getParameter = patchGetParameter(originalGetParam2);
    }
})();
