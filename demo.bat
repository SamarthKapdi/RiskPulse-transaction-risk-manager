@echo off
setlocal enabledelayedexpansion

echo =======================================================
echo RiskPulse --- Explainable AI Transaction Risk Manager
echo =======================================================
echo.
echo Phase 1: Checking Python Environment...

if not exist "venv\Scripts\python.exe" (
    echo [ERROR] Virtual environment not found. Run setup first.
    exit /b 1
)

echo Phase 2: Starting RiskPulse API Server...
start "RiskPulse API" cmd /c ".\venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000"

echo.
echo Waiting for API to start...
timeout /t 5 > nul

echo Phase 3: Opening Dashboard...
start "" "dashboard\index.html"

echo.
echo =======================================================
echo System is running!
echo - API: http://localhost:8000
echo - Swagger Docs: http://localhost:8000/docs
echo - Dashboard opened in your browser
echo.
echo Press any key to stop the server and exit...
pause > nul

taskkill /F /FI "WindowTitle eq RiskPulse API*" > nul 2>&1
echo Stopped.
