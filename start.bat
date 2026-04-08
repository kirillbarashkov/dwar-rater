@echo off
echo Starting Dwar Rater...
cd /d "%~dp0"
docker compose up -d
echo.
echo Waiting for services...
timeout /t 10 /nobreak >nul
echo.
echo Services started:
echo   Backend:  http://localhost:5000
echo   Frontend: http://localhost:5173
echo.
echo Press any key to stop services...
pause >nul
docker compose down