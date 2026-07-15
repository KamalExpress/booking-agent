# Add Push Notification & PWA Setup UI

The user requested a manual configuration setup page to install the app and allow push permissions, restoring the functionality from an earlier UI.

## Proposed Changes

We will add a new "Push Notifications & App Setup" card directly into the existing `settings.html` page. This avoids creating unnecessary extra pages while keeping all configuration in one place.

### [MODIFY] `app/templates/settings.html`

1. **Add a new configuration card**:
   - A button to **"Subscribe to Push Notifications"**.
   - A short helper text explaining how to install the PWA (using the browser's native "Add to Home Screen" or "Install App" functionality).
2. **Add required JavaScript**:
   - Logic to fetch the VAPID public key from `/api/push/vapid-public-key`.
   - Logic to request `Notification.requestPermission()` from the browser.
   - Logic to use the `ServiceWorkerRegistration.pushManager` to subscribe the device.
   - Logic to POST the resulting subscription object to `/api/push/subscribe` with the JWT token.
   - A helper function `urlBase64ToUint8Array` to convert the VAPID key.

## Verification Plan
- We will instruct the user to navigate to the Settings page.
- The user will click "Subscribe to Push Notifications".
- The browser should prompt for notification permissions (if not already granted).
- The subscription should be successfully saved to the backend database.
- The user can then use the "Send Test Push Notif" button on the Diagnostics page to verify delivery.
