@echo off
echo Starting Dwar Rater (development mode)...
cd /d "%~dp0"

echo Installing backend dependencies...
pip install -r backend/requirements.txt >nul 2>&1

echo Starting backend...
start "Backend" cmd /k "cd backend && python -m flask run --host=0.0.0.0 --port=5000"

echo Waiting for backend...
timeout /t 5 /nobreak >nul

echo Starting frontend...
start "Frontend" cmd /k "cd frontend && npm run dev"

echo.
echo Dwar Rater is running:
echo   Backend:  http://localhost:5000
echo   Frontend: http://localhost:5173
echo.
echo Press any key to stop all services...
pause >nul

taskkill /f /im python.exe 2>nul
taskkill /f /im node.exe 2>nul
echo All services stopped.