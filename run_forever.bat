@echo off
REM Sarbon24 — keep the app running; auto-restart if it ever stops.
REM Double-click this file to start. Close the window to stop everything.
title Sarbon24 (keep this window open)
cd /d "%~dp0"
:loop
echo ============================================
echo  Starting Sarbon24 ...  %date% %time%
echo  (web + bot + scheduler)   Keep this open!
echo ============================================
py run_all.py
echo.
echo  Sarbon24 stopped. Restarting in 5 seconds...
echo  (press Ctrl+C now to quit for good)
timeout /t 5 >nul
goto loop
