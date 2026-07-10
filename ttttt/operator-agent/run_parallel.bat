@echo off
if "%~1"=="" (
    set COUNT=5
) else (
    set COUNT=%1
)

set MAX_SLOTS_TO_BOOK=%COUNT%

if exist "booked.txt" del "booked.txt"
if exist "lock.txt" del "lock.txt"

echo Starting %COUNT% parallel mock operators...

FOR /L %%i IN (1, 1, %COUNT%) DO (
    start ..\venv\Scripts\python.exe demo-operator.py
)

echo Operators launched successfully!
