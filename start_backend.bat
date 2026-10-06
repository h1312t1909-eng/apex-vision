@echo off
title CCTV Attendance Backend Server
cd /d "%~dp0"
echo ========================================================
echo Starting CCTV Attendance FastAPI Backend Server...
echo ========================================================
call .\venv\Scripts\activate.bat
python -m uvicorn backend.api.main:app --host 0.0.0.0 --port 8000 --reload
pause
