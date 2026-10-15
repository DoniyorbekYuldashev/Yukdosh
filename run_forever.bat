@echo off
REM Yukdosh — keep the app running; auto-restart if it ever stops.
REM Double-click this file to start. Close the window to stop everything.
title Yukdosh (keep this window open)
cd /d "%~dp0"
:loop
echo ============================================
echo  Starting Yukdosh ...  %date% %time%
echo  (web + bot + scheduler)   Keep this open!
echo ============================================
py run_all.py
echo.
echo  Yukdosh stopped. Restarting in 5 seconds...
echo  (press Ctrl+C now to quit for good)
timeout /t 5 >nul
goto loop
