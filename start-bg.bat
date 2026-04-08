@echo off
echo Starting Dwar Rater...
cd /d "%~dp0"
docker compose up -d
echo.
echo Waiting for services to be ready...
timeout /t 15 /nobreak >nul
echo.
echo Dwar Rater is running:
echo   Backend:  http://localhost:5000
echo   Frontend: http://localhost:5173
echo.
echo To stop: docker compose down
pause