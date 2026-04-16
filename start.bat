@echo off
cd /d "%~dp0"
start "SlideBuddy API" cmd /k "python -m uvicorn slidebuddy.api.app:app --port 8000 --reload"
cd frontend
start "SlideBuddy Web" cmd /k "npx next dev"
echo.
echo SlideBuddy gestartet!
echo   API:  http://localhost:8000
echo   Web:  http://localhost:3000
echo.
