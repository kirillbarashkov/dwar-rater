@echo off
echo Stopping Dwar Rater...
cd /d "%~dp0"
docker compose down
echo.
echo All services stopped.