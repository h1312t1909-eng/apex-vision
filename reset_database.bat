@echo off
title Reset Database Fresh
cd /d "%~dp0"
echo ========================================================
echo Resetting CCTV Attendance Database to Clean Fresh State...
echo ========================================================
call .\venv\Scripts\activate.bat
python -m backend.database.reset_fresh
echo ========================================================
echo Reset Complete!
echo ========================================================
pause
