// Permissions API Spoof
// Returns realistic permission states to prevent detection via permission state enumeration.
// Bot detection services check for unusual permission combinations.

(function () {
    'use strict';

    if (!navigator.permissions || !navigator.permissions.query) return;

    const originalQuery = navigator.permissions.query.bind(navigator.permissions);

    // Realistic permission states for a normal Chrome user
    // "prompt" = never asked (most common for new sessions)
    // "granted" = user allowed
    // "denied" = user blocked
    const permissionStates = {
        'geolocation': 'prompt',
        'notifications': 'prompt',
        'push': 'prompt',
        'midi': 'prompt',
        'camera': 'prompt',
        'microphone': 'prompt',
        'speaker': 'prompt',
        'device-info': 'prompt',
        'background-fetch': 'prompt',
        'background-sync': 'prompt',
        'bluetooth': 'prompt',
        'persistent-storage': 'prompt',
        'ambient-light-sensor': 'prompt',
        'accelerometer': 'prompt',
        'gyroscope': 'prompt',
        'magnetometer': 'prompt',
        'clipboard-read': 'prompt',
        'clipboard-write': 'granted', // Chrome grants this by default
        'payment-handler': 'prompt',
        'screen-wake-lock': 'prompt',
        'nfc': 'prompt',
        'display-capture': 'prompt',
        'idle-detection': 'prompt',
        'periodic-background-sync': 'prompt',
        'system-wake-lock': 'prompt',
        'storage-access': 'prompt',
        'window-management': 'prompt',
        'local-fonts': 'prompt',
        'top-level-storage-access': 'prompt',
    };

    navigator.permissions.query = function (descriptor) {
        const name = descriptor && descriptor.name;

        if (name && permissionStates[name] !== undefined) {
            return Promise.resolve({
                state: permissionStates[name],
                status: permissionStates[name], // Some implementations use 'status'
                onchange: null,
                addEventListener: function () { },
                removeEventListener: function () { },
                dispatchEvent: function () { return true; }
            });
        }

        // For unknown permissions, fall back to original
        return originalQuery(descriptor).catch(function () {
            // If querying fails (unsupported permission), return prompt
            return {
                state: 'prompt',
                status: 'prompt',
                onchange: null,
                addEventListener: function () { },
                removeEventListener: function () { },
                dispatchEvent: function () { return true; }
            };
        });
    };
})();
