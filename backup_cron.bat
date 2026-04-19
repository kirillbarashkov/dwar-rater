@echo off
REM PostgreSQL Backup Script for Windows
REM Schedule via Windows Task Scheduler
REM Example: schtasks /create /tn "Dwar Rater Backup" /tr "python scripts\backup_cron.py" /sc daily /st 03:00

set SCRIPT_DIR=%~dp0
cd /d %SCRIPT_DIR%..
set PYTHONPATH=%SCRIPT_DIR%..
set POSTGRES_PASSWORD=change-me-in-production
set POSTGRES_HOST=localhost
set POSTGRES_PORT=5432
set POSTGRES_DB=dwar_rater
set POSTGRES_USER=dwar

echo === Dwar Rater Backup %date% %time% ===
python scripts\backup_postgres.py --keep 7
echo === Backup Done ===