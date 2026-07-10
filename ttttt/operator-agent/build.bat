@echo off
echo Installing Playwright local browser...
set PLAYWRIGHT_BROWSERS_PATH=0
call ..\venv\Scripts\playwright install chromium

echo Building Portable Executable with PyInstaller...
call ..\venv\Scripts\pyinstaller --noconfirm --onedir --windowed --name "appt-monitor" ^
  --add-data "accounts.json;." ^
  --add-data "settings.json;." ^
  --add-data "..\venv\Lib\site-packages\customtkinter;customtkinter" ^
  --add-data "..\venv\Lib\site-packages\playwright\driver;playwright\driver" ^
  gui.py

echo Done! The portable application is located in the dist\appt-monitor folder.
pause
