# BUILD & DEPLOYMENT GUIDE

## Roshe Group Logistics Portal Management System - Complete Build Instructions

---

If you need deployment scope at a glance, check the [Completion Report Highlights](PROJECT_SUMMARY.md#completion-report-highlights) before building.

## Quick Build Command

For experienced developers, this single command builds everything:

```bash
setup.bat && python manage.py collectstatic --noinput && build.bat
```

---

## Detailed Build Process

### Stage 1: Prepare Development Environment

```bash
# Navigate to project directory
cd Roshe_Logistics_System

# Create virtual environment (optional but recommended)
python -m venv venv
venv\Scripts\activate

# Install all dependencies
pip install -r requirements.txt
```

### Stage 2: Initialize Database

```bash
# Run Django migrations
python manage.py migrate

# Create superuser account for testing
python manage.py createsuperuser
  Username: testadmin
  Email: admin@roshegroup.com
  Password: TestPassword123
```

### Stage 3: Test Application

```bash
# Start development server
python desktop_app.py
# OR
python manage.py runserver

# Test login and navigation
# Verify all modules work correctly
```

### Stage 4: Collect Static Files

```bash
python manage.py collectstatic --noinput
```

### Stage 5: Build Windows Executable

#### Option A: Using Batch File (Recommended)
```bash
build.bat
```

#### Option B: Manual Build with PyInstaller
```bash
pip install --upgrade pyinstaller
pyinstaller roshe_logistics.spec
```

#### Option C: Advanced PyInstaller Build
```bash
pyinstaller \
  --onefile \
  --windowed \
  --icon=roshe_icon.ico \
  --add-data="logistics/templates:logistics/templates" \
  --add-data="logistics/static:logistics/static" \
  --add-data="roshe_logistics:roshe_logistics" \
  --hidden-import=django \
  --hidden-import=pywebview \
  desktop_app.py \
  -n RosheLogistics
```

---

## Output Structure After Build

```
Roshe_Logistics_System/
├── dist/
│   ├── RosheLogistics.exe          ← Main executable
│   ├── RosheLogistics/             ← Supporting files
│   └── ... (runtime dependencies)
│
├── build/
│   └── ... (temporary build files)
│
└── (source files remain)
```

---

## Testing the Built Executable

### Local Testing

1. **Navigate to dist folder:**
   ```bash
   cd dist
   ```

2. **Run the executable:**
   ```bash
   RosheLogistics.exe
   ```

3. **Test functionalities:**
   - [ ] Login works
   - [ ] Dashboard loads
   - [ ] Can view all modules
   - [ ] CRUD operations work
   - [ ] CSV export works
   - [ ] No console errors

### Network Testing

1. Copy `RosheLogistics.exe` to another computer
2. Run without installing anything else (except Python if needed)
3. Verify functionality

---

## Distribution Methods

### Method 1: Direct .exe Distribution

**Best for**: Small teams (1-10 users)

```bash
# Copy single file to users
dist\RosheLogistics.exe

# Users simply run the .exe
# Application works immediately
```

**Advantages**:
- ✅ Simplest distribution
- ✅ No installation needed
- ✅ Portable
- ✅ Works offline

**Disadvantages**:
- ❌ Each user has separate database
- ❌ No data synchronization

### Method 2: Network Shared Database

**Best for**: Teams that need shared data

1. **Set up main computer with database:**
   ```bash
   # On server/shared computer
   python desktop_app.py
   
   # Set up all data
   # Create backup of db.sqlite3
   ```

2. **Share database with other users:**
   ```bash
   # Copy db.sqlite3 to network share
   copy db.sqlite3 \\network_server\shared_databases\
   ```

3. **Configure other users:**
   ```python
   # In settings.py on user machines
   DATABASES = {
       'default': {
           'ENGINE': 'django.db.backends.sqlite3',
           'NAME': r'\\network_server\shared_databases\db.sqlite3',
       }
   }
   ```

4. **Rebuild .exe with network database path**

### Method 3: Professional Installer (NSIS)

**Best for**: Enterprise deployment

1. **Install NSIS:**
   - Download from https://nsis.sourceforge.io/
   - Run installer

2. **Create installer script (`installer.nsi`):**
   ```nsis
   ; Roshe Group Logistics Portal Installer Script
   !include "MUI2.nsh"
   !include "x64.nsh"
   
   ; Configuration
   Name "Roshe Group Logistics Portal Management System v1.0"
   OutFile "RosheLogistics_Setup_v1.0.exe"
   InstallDir "$PROGRAMFILES\Roshe Group Logistics Portal"
   InstallDirRegKey HKCU "Software\Roshe Group Logistics Portal" "Install_Dir"
   RequestExecutionLevel admin
   
   ; Modern UI
   !insertmacro MUI_PAGE_WELCOME
   !insertmacro MUI_PAGE_DIRECTORY
   !insertmacro MUI_PAGE_INSTFILES
   !insertmacro MUI_PAGE_FINISH
   !insertmacro MUI_LANGUAGE "English"
   
   Section "Install"
     SetOutPath "$INSTDIR"
     
     ; Copy application files
     File "dist\RosheLogistics.exe"
     File "README.md"
     File "INSTALLATION_GUIDE.md"
     
     ; Create shortcuts
     CreateDirectory "$SMPROGRAMS\Roshe Group Logistics Portal"
     CreateShortCut "$SMPROGRAMS\Roshe Group Logistics Portal\Roshe Group Logistics Portal.lnk" "$INSTDIR\RosheLogistics.exe"
     CreateShortCut "$SMPROGRAMS\Roshe Group Logistics Portal\Uninstall.lnk" "$INSTDIR\Uninstall.exe"
     CreateShortCut "$DESKTOP\Roshe Group Logistics Portal.lnk" "$INSTDIR\RosheLogistics.exe"
     
     ; Write uninstaller
     WriteUninstaller "$INSTDIR\Uninstall.exe"
     WriteRegStr HKCU "Software\Roshe Group Logistics Portal" "Install_Dir" "$INSTDIR"
   SectionEnd
   
   Section "Uninstall"
     Delete "$INSTDIR\*.*"
     RMDir "$INSTDIR"
     Delete "$SMPROGRAMS\Roshe Group Logistics Portal\*.*"
     RMDir "$SMPROGRAMS\Roshe Group Logistics Portal"
     Delete "$DESKTOP\Roshe Group Logistics Portal.lnk"
   SectionEnd
   ```

3. **Build installer:**
   ```bash
   makensis installer.nsi
   ```

4. **Distribute:**
   ```bash
   RosheLogistics_Setup_v1.0.exe
   ```

---

## Deployment Checklist

### Pre-Deployment

- [ ] All tests pass
- [ ] Database is properly initialized
- [ ] Static files are collected
- [ ] Documentation is complete
- [ ] Version number is updated
- [ ] Changelog is prepared

### Deployment

- [ ] Back up original database
- [ ] Deploy to test environment first
- [ ] Verify all features in test environment
- [ ] Train users
- [ ] Deploy to production
- [ ] Monitor for issues

### Post-Deployment

- [ ] Verify users can access
- [ ] Check that data syncs correctly
- [ ] Monitor error logs
- [ ] Collect user feedback
- [ ] Plan updates and improvements

---

## Version Management

### Version Numbering
Use semantic versioning: `MAJOR.MINOR.PATCH`

- `1.0.0` - Initial release
- `1.1.0` - New features
- `1.0.1` - Bug fixes

### Maintaining Versions

```bash
# In README.md and build files, update:
- Version number
- Release date
- Change log

# Tag releases
git tag -a v1.0.0 -m "Release version 1.0.0"
```

### Update Packages

To update dependencies safely:

```bash
# Check for updates
pip list --outdated

# Update specific package
pip install --upgrade Django

# Update all
pip install --upgrade -r requirements.txt

# Rebuild .exe
build.bat
```

---

## Database Migration for Updates

When deploying updates to multiple computers:

1. **Test migrations:**
   ```bash
   python manage.py migrate --plan
   ```

2. **Create migration:**
   ```bash
   python manage.py makemigrations
   python manage.py migrate
   ```

3. **Distribute updated .exe:**
   ```bash
   # New .exe includes updated models
   build.bat
   ```

4. **Users run new version:**
   - Close old version
   - Replace with new .exe
   - Database auto-migrates on first run

---

## Troubleshooting Builds

### Build Fails with "Not Found" Error

```bash
# Clean previous builds
rmdir /s /q build
rmdir /s /q dist
del *.spec

# Verify all files exist
dir logistics\templates
dir logistics\static

# Rebuild
pyinstaller roshe_logistics.spec
```

### Executable Size Too Large

```bash
# Use --onefile option (larger single file, easier distribution)
pyinstaller --onefile desktop_app.py -n RosheLogistics

# Or use --distpath for smaller distribution
pyinstaller --distpath "dist_slim" roshe_logistics.spec
```

### Executable Won't Run

```bash
# Check Windows Defender/Antivirus isn't blocking
# Allow through firewall if needed
# Try running as Administrator
# Check for missing DLL files (shouldn't happen with PyInstaller)
```

### Database Not Included in Build

Ensure in `roshe_logistics.spec`:
```python
datas=[
    ('db.sqlite3', '.'),  # Include database
    ('logistics/templates', 'logistics/templates'),
    ('logistics/static', 'logistics/static'),
]
```

---

## Performance Optimization

### For Faster Builds

```bash
# Skip unnecessary modules
--exclude-module=numpy
--exclude-module=scipy

# Use UPX compression (optional)
--upx-exclude=vcruntime140.dll
```

### For Faster Runtime

1. **Optimize database:**
   ```bash
   python manage.py dbshell
   VACUUM;  # SQLite command
   ANALYZE; # SQLite command
   ```

2. **Cache static files:**
   ```python
   # In settings.py
   CACHES = {
       'default': {
           'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
           'LOCATION': 'roshe-cache',
       }
   }
   ```

---

## Security for Distribution

### Before Distribution

1. **Set DEBUG = False in settings.py**
   ```python
   DEBUG = False
   ALLOWED_HOSTS = ['127.0.0.1', 'localhost']
   ```

2. **Generate strong SECRET_KEY:**
   ```python
   from django.core.management.utils import get_random_secret_key
   print(get_random_secret_key())
   ```

3. **Set secure cookie settings:**
   ```python
   SESSION_COOKIE_SECURE = False  # False for offline
   CSRF_COOKIE_SECURE = False     # False for offline
   ```

4. **Remove debug information:**
   ```bash
   python manage.py check --deploy
   ```

### After Distribution

1. **Monitor access logs:**
   ```bash
   tail -f logistics.log
   ```

2. **Keep Python updated:**
   ```bash
   python -m pip install --upgrade pip
   ```

3. **Update dependencies regularly:**
   ```bash
   pip install --upgrade -r requirements.txt
   ```

---

## Backup & Recovery

### Automatic Backups

Create backup script (`backup.bat`):
```batch
@echo off
for /f "tokens=2-4 delims=/ " %%a in ('date /t') do (set mydate=%%c%%a%%b)
for /f "tokens=1-2 delims=/:" %%a in ('time /t') do (set mytime=%%a%%b)

copy db.sqlite3 backups\db_%mydate%_%mytime%.sqlite3

echo Backup completed: backups\db_%mydate%_%mytime%.sqlite3
```

Run regularly:
```bash
# Windows Task Scheduler
# Set to run daily at 2:00 PM
backup.bat
```

### Restore from Backup

```bash
# Stop application
# Copy backup file
copy backups\db_20250101_1400.sqlite3 db.sqlite3

# Restart application
python desktop_app.py
```

---

## Final Build Command Summary

```bash
# Complete build pipeline
setup.bat && ^
python manage.py collectstatic --noinput && ^
build.bat && ^
echo Build complete! Find executable in: dist\RosheLogistics.exe
```

---

**Your Roshe Group Logistics Portal Management System is ready for deployment!**
