# Sprint 6: Push Notifications & App Setup

We've successfully added a manual configuration section for PWA Installation and Push Notification Subscriptions.

## What Changed
- **`app/templates/settings.html`**: Added a new configuration card titled "Push Notifications & App Setup".
- **Added JavaScript Subscription Logic**:
  - Automatically fetches the `VAPID_PUBLIC_KEY` from the `/api/push/vapid-public-key` endpoint.
  - Utilizes `Notification.requestPermission()` to securely ask for browser notification rights.
  - Hooks into the Service Worker via `registration.pushManager.subscribe()` to generate a unique subscription token for the device.
  - Securely POSTs this subscription to `/api/push/subscribe` using the user's JWT `Authorization` header.

## How to Test
1. Make sure you have pulled and redeployed the latest container in Portainer.
2. Open the SaaS in your mobile browser.
3. Use your browser menu to "Add to Home Screen" or "Install App". This will install the PWA natively on your phone.
4. Open the newly installed app from your home screen.
5. Navigate to the **Settings** page from the sidebar menu.
6. Click the new **Subscribe to Push Notifications** button.
7. Allow notifications when prompted by your OS.
8. Wait for the green success message!
9. You can then go to the **Diagnostics** page and click "Send Test Push" to verify it arrives instantly.
