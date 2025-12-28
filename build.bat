@echo off
REM Build script for creating Windows executable

echo.
echo ================================================
echo Building Roshe Group Logistics Portal Windows Executable
echo ================================================
echo.

REM Check if pyinstaller is installed
python -m pip show pyinstaller > nul
if %errorlevel% neq 0 (
    echo Installing PyInstaller...
    pip install pyinstaller
)

REM Collect static files
echo.
echo Collecting static files...
python manage.py collectstatic --noinput

REM Build executable
echo.
echo Building executable... This may take a few minutes...
pyinstaller roshe_logistics.spec

echo.
echo ================================================
echo Build Complete!
echo ================================================
echo.
echo Your executable is located at:
echo   dist\RosheLogistics.exe
echo.
echo You can now distribute this .exe file to other computers.
echo.
pause
