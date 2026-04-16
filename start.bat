@echo off
cd /d "%~dp0"
start "SlideBuddy API" cmd /k ".venv\Scripts\python.exe -m uvicorn slidebuddy.api.app:app --port 8000 --reload --reload-dir slidebuddy"
cd frontend
start "SlideBuddy Web" cmd /k "npx next dev"
echo.
echo SlideBuddy gestartet!
echo   API:  http://localhost:8000
echo   Web:  http://localhost:3000
echo.
