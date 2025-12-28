# INSTALLATION GUIDE

## Roshe Group Logistics Portal Management System - Complete Setup Instructions

### Table of Contents
1. [System Requirements](#system-requirements)
2. [Step-by-Step Installation](#step-by-step-installation)
3. [Running the Application](#running-the-application)
4. [Building the Executable](#building-the-executable)
5. [Distribution & Deployment](#distribution--deployment)
6. [Troubleshooting](#troubleshooting)

---

For a quick audit of what ships in this release, review the [Completion Report Highlights](PROJECT_SUMMARY.md#completion-report-highlights).

## System Requirements

### Minimum Requirements
- **Operating System**: Windows 10 or higher (64-bit recommended)
- **Memory**: 4 GB RAM
- **Disk Space**: 500 MB (for installation)
- **Python**: Version 3.9 or higher

### Recommended Requirements
- **Operating System**: Windows 10/11 (Latest updates)
- **Memory**: 8 GB RAM
- **Disk Space**: 1 GB
- **Internet**: For initial setup and package installation

---

## Step-by-Step Installation

### Step 1: Install Python

1. **Download Python**
   - Visit https://www.python.org/downloads/
   - Download Python 3.9 or higher (latest version recommended)
   - Choose "Windows installer (64-bit)"

2. **Run Python Installer**
   - Double-click the downloaded `.exe` file
   - **IMPORTANT**: Check "Add Python to PATH" ✓
   - Click "Install Now"
   - Wait for installation to complete
   - Click "Close"

3. **Verify Python Installation**
   - Open Command Prompt (Press `Win + R`, type `cmd`)
   - Type: `python --version`
   - Should show: `Python 3.x.x`

### Step 2: Extract Project Files

1. Extract the `Roshe_Logistics_System` folder to your desired location
2. Open Command Prompt
3. Navigate to the project folder:
   ```bash
   cd C:\Users\YourUsername\Desktop\Roshe_Logistics_System
   ```

### Step 3: Install Dependencies

#### Option A: Interactive Setup (Recommended)

Run the interactive setup wizard:
```bash
setup_interactive.bat
```

This will guide you through:
1. **Feature Selection**
   - Core System (Required)
     - Client Management
     - Loading/Cargo Management
     - Transit Management
     - Payment Management
     - Container Returns
   
   - Optional Features (Choose which to include)
     - Audit Logging & Activity Tracking
     - Reports Dashboard
     - CSV Export Functionality
     - Roshe Group Logo & Branding
   
   - Extras
     - Create Desktop Shortcut

2. **Dependency Installation**
   - Install all required Python packages
   - Create the SQLite database
   - Prompt you to create an admin account

#### Option B: Simple Setup (Default)

Run the basic setup batch file:
```bash
setup.bat
```

This installs:
- All required Python packages
- Creates the SQLite database
- Creates an admin account
- Includes all features by default

#### Option C: Manual Installation

Run these commands step by step:

```bash
# Install packages
pip install -r requirements.txt

# Run migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser
```

When creating superuser, follow the prompts:
```
Username: admin
Email: admin@roshegroup.com
Password: (choose a strong password)
Password (again): (repeat)
```

---

## Feature Selection Details

### Core Features (Always Installed)
- **Client Management** - Add, edit, view clients
- **Loading/Cargo** - Manage shipments and cargo
- **Transit Management** - Track vessels and shipments
- **Payment Management** - Manage payments and balances
- **Container Returns** - Track container returns

### Optional Features

#### 1. Audit Logging (Recommended)
- Tracks all user activity
- Records create, update, delete operations
- Maintains activity history
- Helps with compliance and troubleshooting
- **Storage**: Minimal (SQLite)
- **Performance Impact**: Negligible

#### 2. Reports Dashboard (Recommended)
- View system statistics
- Client reports
- Shipment summaries
- Payment analytics
- Container return reports
- **Helps with**: Business analysis and decision-making

#### 3. CSV Export (Recommended)
- Export clients to CSV
- Export shipments to CSV
- Export payments to CSV
- Export container returns to CSV
- **Use for**: Data analysis, Excel reports, backups

#### 4. Roshe Group Logo & Branding
- Official Roshe Group logo in UI header
- Branded color scheme (Dark Blue #003366, Yellow #FFD700)
- Company contact information display
- Professional appearance
- **Installation**: Interactive setup will guide you
  - Logo will be downloaded from company server
  - Branding colors auto-applied throughout UI

### Desktop Shortcut
- Creates "Roshe Group Logistics Portal" shortcut on Desktop
- Quick access to launch application
- Recommended for all users

### Step 4: Verify Installation

Run the application:
```bash
python run.py
```

A window should open showing the login page. Login with your credentials.

---

## Running the Application

### Method 1: Quick Start (Recommended)
```bash
python run.py
```

### Method 2: Desktop Application
```bash
python desktop_app.py
```

### Method 3: Web Browser (Development)
```bash
python manage.py runserver
```
Then open: `http://127.0.0.1:8000/login/`

### Method 4: Using Batch File
Create a shortcut to `run.py` on your desktop for easy access.

---

## Building the Executable

### Prerequisites
Make sure all dependencies are installed:
```bash
pip install pyinstaller
```

### Build Steps

1. **Prepare the build:**
   ```bash
   python manage.py collectstatic --noinput
   ```

2. **Build the executable:**
   ```bash
   build.bat
   ```
   
   OR manually:
   ```bash
   pyinstaller roshe_logistics.spec
   ```

3. **Locate the executable:**
   - Navigate to `dist` folder
   - Find `RosheLogistics.exe`

### Testing the Executable

1. Copy `RosheLogistics.exe` to a different location
2. Double-click to run
3. Verify all functions work correctly

### Build Troubleshooting

If build fails:
```bash
# Clean previous builds
rmdir /s build
rmdir /s dist
del *.spec

# Try building again
pyinstaller roshe_logistics.spec
```

---

## Distribution & Deployment

### For Single Computer

1. Build the executable as described above
2. Double-click `RosheLogistics.exe` to install
3. Share the database file with other computers (optional)

### For Multiple Computers

#### Option A: Distribute Standalone .exe
1. Build the executable
2. Copy `dist\RosheLogistics.exe` to users
3. Users run the .exe on their computers
4. Each computer has its own database

#### Option B: Share Database
1. After setup on main computer, copy `db.sqlite3`
2. Place copy in shared network location
3. Modify `settings.py` to point to shared database:
   ```python
   DATABASES = {
       'default': {
           'ENGINE': 'django.db.backends.sqlite3',
           'NAME': r'\\network_path\db.sqlite3',
       }
   }
   ```

#### Option C: Create Network Deployment
1. Install on central server
2. Distribute database to other computers
3. Use Django's multi-user features
4. Implement database synchronization

### Creating a Windows Installer (NSIS)

For professional distribution:

1. Install NSIS from https://nsis.sourceforge.io/
2. Create `installer.nsi`:
   ```nsis
   ; Roshe Group Logistics Portal Installer
   !include "MUI2.nsh"
   
   Name "Roshe Group Logistics Portal Management System"
   OutFile "RosheLogistics_Installer.exe"
   InstallDir "$PROGRAMFILES\Roshe Group Logistics Portal"
   
   !insertmacro MUI_PAGE_DIRECTORY
   !insertmacro MUI_PAGE_INSTFILES
   !insertmacro MUI_LANGUAGE "English"
   
   Section "Install"
     SetOutPath "$INSTDIR"
     File "dist\RosheLogistics.exe"
     CreateShortCut "$SMPROGRAMS\Roshe Group Logistics Portal.lnk" "$INSTDIR\RosheLogistics.exe"
     CreateShortCut "$DESKTOP\Roshe Group Logistics Portal.lnk" "$INSTDIR\RosheLogistics.exe"
   SectionEnd
   ```

3. Build with NSIS:
   ```bash
   makensis installer.nsi
   ```

4. Distribute `RosheLogistics_Installer.exe`

---

## Troubleshooting

### Issue 1: Python Not Found
**Error**: `'python' is not recognized as an internal or external command`

**Solution**:
1. Reinstall Python
2. Ensure "Add Python to PATH" is checked
3. Restart Command Prompt after installation

### Issue 2: Permission Denied
**Error**: `Permission denied` when running setup

**Solution**:
1. Right-click Command Prompt
2. Select "Run as administrator"
3. Run the setup command again

### Issue 3: Database Locked
**Error**: `database is locked`

**Solution**:
1. Close all instances of the application
2. Delete `db.sqlite3` if starting fresh
3. Restart the application

### Issue 4: Port Already in Use
**Error**: `Port 8000 is already in use`

**Solution**:
Edit `desktop_app.py` and change:
```python
sys.argv = ['manage.py', 'runserver', '127.0.0.1:8001']
```

### Issue 5: Missing Dependencies
**Error**: `ModuleNotFoundError` or `ImportError`

**Solution**:
```bash
# Reinstall all dependencies
pip install --upgrade -r requirements.txt

# Clear pip cache
pip cache purge

# Try installation again
pip install -r requirements.txt
```

### Issue 6: Build Fails
**Error**: PyInstaller build error

**Solution**:
```bash
# Clean previous builds
rmdir /s /q build
rmdir /s /q dist

# Upgrade PyInstaller
pip install --upgrade pyinstaller

# Rebuild
pyinstaller roshe_logistics.spec
```

### Issue 7: Static Files Not Loading
**Error**: CSS/JS not loading in web interface

**Solution**:
```bash
python manage.py collectstatic --noinput
```

### Issue 8: Cannot Connect to Application
**Error**: `Connection refused` or `localhost refused to connect`

**Solution**:
1. Ensure Django is running in background
2. Wait 5-10 seconds after starting for server to initialize
3. Check firewall settings
4. Try different port if 8000 is blocked

---

## Advanced Configuration

### Environment Variables

Create `.env` file in project root:
```
DEBUG=False
SECRET_KEY=your-secret-key-here
ALLOWED_HOSTS=127.0.0.1,localhost
DATABASE_URL=sqlite:///db.sqlite3
```

### Database Backup

Regular backups of `db.sqlite3`:
```bash
# Create backup
copy db.sqlite3 db.sqlite3.backup

# Restore from backup
copy db.sqlite3.backup db.sqlite3
```

### Logging Configuration

Enable detailed logging by adding to `settings.py`:
```python
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': 'logistics.log',
        },
    },
    'root': {
        'handlers': ['file'],
        'level': 'INFO',
    },
}
```

---

## Getting Help

If you encounter issues:

1. **Check the logs**: Open `logistics.log` for detailed error messages
2. **Review documentation**: Read README.md for comprehensive guide
3. **Contact Roshe Group**:
   - Phone: +256 788 239000 | +8613416137544
   - Email: info@roshegroup.com | roshegroup@gmail.com
   - Address: Plot 13 Mukwano Courts, Buganda Road, floor 2 Room 201–202 I

---

## Next Steps

After successful installation:

1. ✅ Create user accounts for team members
2. ✅ Set up client records
3. ✅ Configure default settings
4. ✅ Train users on system usage
5. ✅ Set up regular database backups
6. ✅ Document custom workflows

---

**Congratulations! Your Roshe Group Logistics Portal Management System is now ready for use.**
