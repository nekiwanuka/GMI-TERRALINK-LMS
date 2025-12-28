@echo off
REM Setup script for Roshe Group Logistics Portal System (Windows)

echo.
echo ================================================
echo Roshe Group Logistics Portal Management System Setup
echo ================================================
echo.

REM Check if Python is installed
echo Checking Python installation...
python --version
if %errorlevel% neq 0 (
    echo ERROR: Python is not installed or not in PATH
    exit /b 1
)

REM Install dependencies
echo.
echo Installing dependencies...
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo ERROR: Failed to install dependencies
    exit /b 1
)

REM Run migrations
echo.
echo Running database migrations...
python manage.py migrate
if %errorlevel% neq 0 (
    echo ERROR: Failed to run migrations
    exit /b 1
)

REM Create superuser
echo.
echo Creating superuser account...
python manage.py createsuperuser

echo.
echo ================================================
echo Setup Complete!
echo ================================================
echo.
echo To start the application, run:
echo   python desktop_app.py
echo.
echo For development mode (browser):
echo   python manage.py runserver
echo.
pause
