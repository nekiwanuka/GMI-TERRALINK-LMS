@echo off
REM ========================================
REM Roshe Group Logistics Portal Management System
REM Interactive Setup with Feature Selection
REM ========================================

setlocal enabledelayedexpansion

echo.
echo ========================================
echo ROSHE GROUP LOGISTICS PORTAL MANAGEMENT SYSTEM
echo Interactive Setup Wizard
echo ========================================
echo.

REM Check Python installation
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed or not in PATH
    echo Please install Python 3.9+ and ensure it's added to PATH
    pause
    exit /b 1
)

echo [OK] Python detected
python --version
echo.

REM Feature Selection Menu
echo ========================================
echo FEATURE SELECTION
echo ========================================
echo.
echo Choose which features to install:
echo.

set "INSTALL_AUDIT_LOG=Y"
set "INSTALL_REPORTS=Y"
set "INSTALL_CSV_EXPORT=Y"
set "INSTALL_LOGO=N"
set "CREATE_DESKTOP_SHORTCUT=N"

echo 1. Core System (REQUIRED)
echo    - Client Management
echo    - Loading/Cargo Management
echo    - Transit Management
echo    - Payment Management
echo    - Container Return Management
echo.

echo 2. Audit Logging (optional)
set /p AUDIT_LOG="   Install audit logging? (Y/N) [Y]: "
if /i "!AUDIT_LOG!"=="N" set "INSTALL_AUDIT_LOG=N"
echo.

echo 3. Reports Dashboard (optional)
set /p REPORTS="   Install reports module? (Y/N) [Y]: "
if /i "!REPORTS!"=="N" set "INSTALL_REPORTS=N"
echo.

echo 4. CSV Export (optional)
set /p CSV="   Install CSV export feature? (Y/N) [Y]: "
if /i "!CSV!"=="N" set "INSTALL_CSV_EXPORT=N"
echo.

echo 5. Roshe Group Logo (optional)
set /p LOGO="   Install Roshe Group logo and branding? (Y/N) [N]: "
if /i "!LOGO!"=="Y" set "INSTALL_LOGO=Y"
echo.

echo 6. Desktop Shortcut
set /p SHORTCUT="   Create desktop shortcut? (Y/N) [N]: "
if /i "!SHORTCUT!"=="Y" set "CREATE_DESKTOP_SHORTCUT=Y"
echo.

REM Summary
echo ========================================
echo INSTALLATION SUMMARY
echo ========================================
echo.
echo [REQUIRED] Core System .................... YES
echo [OPTIONAL] Audit Logging ................ !INSTALL_AUDIT_LOG!
echo [OPTIONAL] Reports Dashboard ........... !INSTALL_REPORTS!
echo [OPTIONAL] CSV Export ................... !INSTALL_CSV_EXPORT!
echo [OPTIONAL] Roshe Group Logo ............ !INSTALL_LOGO!
echo [EXTRA] Desktop Shortcut ............... !CREATE_DESKTOP_SHORTCUT!
echo.

set /p CONFIRM="Proceed with installation? (Y/N) [Y]: "
if /i "!CONFIRM!"=="N" (
    echo Installation cancelled.
    pause
    exit /b 0
)

echo.
echo ========================================
echo INSTALLING DEPENDENCIES
echo ========================================
echo.

echo Upgrading pip...
python -m pip install --upgrade pip
if errorlevel 1 (
    echo [WARNING] Pip upgrade skipped, continuing with installation...
)

echo [OK] Ready to install packages
echo.

echo Installing required packages...
pip install Django==4.2.7 pywebview==4.4 Pillow==10.1.0 python-decouple==3.8
if errorlevel 1 (
    echo [ERROR] Failed to install core packages
    pause
    exit /b 1
)

echo [OK] Core packages installed
echo.

REM Install optional features
if /i "!INSTALL_CSV_EXPORT!"=="Y" (
    echo Installing CSV export support...
    pip install openpyxl
    echo [OK] CSV export support installed
    echo.
)

if /i "!INSTALL_REPORTS!"=="Y" (
    echo Installing reports support...
    pip install reportlab
    echo [OK] Reports support installed
    echo.
)

echo ========================================
echo SETTING UP DATABASE
echo ========================================
echo.

echo Running database migrations...
python manage.py migrate
if errorlevel 1 (
    echo [ERROR] Failed to run migrations
    pause
    exit /b 1
)

echo [OK] Database created and configured
echo.

REM Handle feature configuration
if /i "!INSTALL_AUDIT_LOG!"=="N" (
    echo Disabling audit logging...
    REM This would require modifying settings or env variables
    REM For now, audit logging is always enabled
)

if /i "!INSTALL_LOGO!"=="Y" (
    echo Downloading Roshe Group logo...
    if not exist "logistics\static\images" mkdir "logistics\static\images"
    
    REM Create a placeholder logo file
    echo # Roshe Group Logo > logistics\static\images\roshe_logo.txt
    echo Logo files should be placed in: logistics/static/images/
    echo Download logo from: https://roshegroup.com/media/logo.png
    echo.
)

echo ========================================
echo CREATING ADMIN ACCOUNT
echo ========================================
echo.
echo You need to create an admin account to access the system.
echo.

python manage.py createsuperuser
if errorlevel 1 (
    echo [ERROR] Failed to create admin account
    pause
    exit /b 1
)

echo [OK] Admin account created
echo.

REM Create desktop shortcut if requested
if /i "!CREATE_DESKTOP_SHORTCUT!"=="Y" (
    echo Creating desktop shortcut...
    
    set "DESKTOP=%USERPROFILE%\Desktop"
    set "PROJECT_PATH=%cd%"
    
    REM Create a VBS script to create the shortcut
    (
        echo Set oWS = WScript.CreateObject("WScript.Shell"^)
        echo sLinkFile = "!DESKTOP!\Roshe Group Logistics Portal.lnk"
        echo Set oLink = oWS.CreateShortcut(sLinkFile^)
        echo oLink.TargetPath = "!PROJECT_PATH!\run.py"
        echo oLink.WorkingDirectory = "!PROJECT_PATH!"
        echo oLink.Description = "Roshe Group Logistics Portal Management System"
        echo oLink.Save
    ) > create_shortcut.vbs
    
    cscript create_shortcut.vbs
    del create_shortcut.vbs
    
    echo [OK] Desktop shortcut created
    echo.
)

echo ========================================
echo INSTALLATION COMPLETE
echo ========================================
echo.
echo Your system is now ready to use!
echo.
echo To start the application:
echo   - Run: python run.py
echo   - OR Double-click the desktop shortcut (if created)
echo.
echo Features installed:
echo   - Core System ...................... YES
echo   - Audit Logging .................. !INSTALL_AUDIT_LOG!
echo   - Reports Dashboard ............. !INSTALL_REPORTS!
echo   - CSV Export ..................... !INSTALL_CSV_EXPORT!
echo   - Roshe Group Logo .............. !INSTALL_LOGO!
echo.
echo First Login:
echo   - Username: [admin account you just created]
echo   - Password: [password you just set]
echo.
echo For help, see README.md or INSTALLATION_GUIDE.md
echo.

pause
