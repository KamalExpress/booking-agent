@echo off
echo Starting Chrome with Remote Debugging enabled on port 9222...
echo Using a dedicated profile so you don't have to close your main Chrome windows!
start "" "C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir="%~dp0chrome-devops-profile"
