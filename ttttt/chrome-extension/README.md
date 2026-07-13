# Kamal Express Captcha Spoofer

This is an internal Chrome extension for Kamal Express staff members. 
Because the booking website heavily restricts their Google reCAPTCHA widget to their own domain, the widget will normally fail to load on our SaaS dashboard (`keagent.alamiaconnect.com`). 

This lightweight extension intercepts background requests to Google reCAPTCHA originating from the dashboard and silently overrides the `Origin` and `Referer` headers to spoof the target website. This allows the widget to render properly so staff members can solve the Captchas manually.

## Installation Instructions (Developer Mode)

Since this is an internal tool, it is not published to the Chrome Web Store. Staff must install it manually:

1. Download this folder (`chrome-extension`) to your computer.
2. Open Google Chrome.
3. Type `chrome://extensions/` in your address bar and hit Enter.
4. In the top right corner, toggle the **Developer mode** switch to **ON**.
5. Click the **Load unpacked** button in the top left.
6. Select the `chrome-extension` folder that you downloaded.
7. Make sure the extension appears in your list and is enabled!

That's it! When you go to the Live Bot Terminal on the SaaS dashboard, the Captchas will now load smoothly without any "Invalid domain" errors.
