@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo === Starting Dwar Rater Project ===
docker compose up -d
echo.
echo Waiting for services...
timeout /t 5 /nobreak >nul
echo.
echo === Services Status ===
docker compose ps
echo.
echo Frontend: http://localhost:5173
echo Backend:  http://localhost:5000
echo.
echo Press any key to close...
pause >nul