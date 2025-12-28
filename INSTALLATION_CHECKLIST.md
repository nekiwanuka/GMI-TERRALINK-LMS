# INSTALLATION CHECKLIST

## Roshe Group Logistics Portal Management System - Setup Verification

---

## 📋 PRE-INSTALLATION CHECKLIST

Before starting installation, verify the following:

### System Requirements
- [ ] Windows 10 or higher
- [ ] 4GB RAM minimum (8GB recommended)
- [ ] 500MB free disk space
- [ ] Internet connection (for initial setup only)

### Python Setup
- [ ] Python 3.9+ downloaded
- [ ] Python installer run with "Add Python to PATH" checked
- [ ] Verified: `python --version` shows 3.9+
- [ ] Verified: `pip --version` works

---

## 🔧 INSTALLATION STEPS

### Step 1: Extract Project
- [ ] Extract `Roshe_Logistics_System` folder to desired location
- [ ] Navigate to project folder in Command Prompt
- [ ] Verify: Can see `setup_interactive.bat`, `setup.bat`, `manage.py`

### Step 2: Choose Installation Method

#### Method A: Interactive Setup (Recommended) ✨
```bash
setup_interactive.bat
```

**During interactive setup, you will choose:**
- [ ] Install Audit Logging? (Y/N)
- [ ] Install Reports Dashboard? (Y/N)
- [ ] Install CSV Export? (Y/N)
- [ ] Install Roshe Group Logo? (Y/N)
- [ ] Create Desktop Shortcut? (Y/N)

**Then verify:**
- [ ] All required packages installed
- [ ] Database created (check for `db.sqlite3`)
- [ ] Admin account created successfully

#### Method B: Automatic Setup (All Features)
```bash
setup.bat
```

**Then verify:**
- [ ] All packages installed (pip output shows "Successfully installed")
- [ ] Database exists: `db.sqlite3` file appears in project folder
- [ ] Admin account created

#### Method C: Manual Setup
```bash
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
```

**Then verify:**
- [ ] Packages installed: Django, pywebview, Pillow, PyInstaller
- [ ] Database created: `db.sqlite3` file exists
- [ ] Superuser created: username and password saved securely

### Step 3: Logo Installation (If Selected)
```bash
python install_logo.py
```

**Verify:**
- [ ] New directories created: `logistics/static/images/`
- [ ] Logo file created: `logistics/static/images/roshe_logo.svg`
- [ ] Branding CSS created: `logistics/static/css/branding.css`
- [ ] Output shows "✓ INSTALLATION COMPLETE"

**Download official logo:**
- [ ] Visit: https://roshegroup.com/media/logo.png
- [ ] Download official Roshe Group logo
- [ ] Replace sample logo: `logistics/static/images/roshe_logo.svg`

---

## ✅ VERIFICATION CHECKLIST

### Files & Directories
- [ ] Project folder exists with all subdirectories
- [ ] `roshe_logistics/` folder contains settings.py, urls.py, etc.
- [ ] `logistics/` folder contains models.py, views.py, forms.py, etc.
- [ ] `logistics/templates/` contains all HTML files
- [ ] `logistics/static/` contains CSS and JS directories
- [ ] `db.sqlite3` database file exists
- [ ] `requirements.txt` contains all dependencies
- [ ] `manage.py` exists in project root

### Python Environment
- [ ] `python --version` returns 3.9+
- [ ] `pip list` shows Django, pywebview, Pillow, PyInstaller
- [ ] No error messages when importing: `import django`, `import pywebview`

### Database
- [ ] `python manage.py makemigrations` shows "No changes detected"
- [ ] `python manage.py migrate` shows "Operations to perform" completed
- [ ] Admin can access database through Django admin

### Application Setup
- [ ] Superuser (admin) account created with username and password
- [ ] Admin account has role set to "superuser"
- [ ] Desktop shortcut created (if selected): Check Desktop for "Roshe Group Logistics Portal"

---

## 🚀 LAUNCH VERIFICATION

### Before First Launch
- [ ] All installation steps completed
- [ ] All verification checks passed
- [ ] Admin credentials saved somewhere secure
- [ ] Superuser account created

### First Launch
```bash
python run.py
```

**Verify during launch:**
- [ ] A new window opens titled "Roshe Group Logistics Portal Management System"
- [ ] Window dimensions are approximately 1400x900
- [ ] Login page loads (shows username/password fields)
- [ ] No error messages in console

### First Login
- [ ] Username: [admin username you created]
- [ ] Password: [admin password you created]
- [ ] Click "Login"

**After login, verify:**
- [ ] Dashboard page loads
- [ ] Sidebar shows navigation menu
- [ ] Welcome message displays "Hello, [admin username]"
- [ ] No error messages or broken pages

### Navigate Through Modules
- [ ] Click "Clients" → loads client list page
- [ ] Click "Cargo/Loading" → loads loading list page
- [ ] Click "Transit" → loads transit list page
- [ ] Click "Payments" → loads payment list page
- [ ] Click "Containers" → loads container list page
- [ ] Click "Reports" → loads reports page with export buttons

### Test Optional Features

#### If Audit Logging Installed
- [ ] Click "Users" (admin menu) → shows user list
- [ ] Click "Audit Logs" (admin menu) → shows activity log
- [ ] Verify log entries are created when you perform actions

#### If Reports Dashboard Installed
- [ ] Reports page shows 4 stat cards
- [ ] Reports page shows data totals (clients, cargo, payments, containers)

#### If CSV Export Installed
- [ ] On Reports page, click "Export Clients" → downloads CSV file
- [ ] Downloaded file opens in Excel/spreadsheet
- [ ] CSV contains client data with proper headers

#### If Roshe Logo Installed
- [ ] Application header shows Roshe Group branding
- [ ] Colors are Dark Blue (#003366) and Yellow (#FFD700)
- [ ] Logo appears in top-left of interface
- [ ] Footer shows Roshe Group contact information

---

## 📊 FEATURE INSTALLATION VERIFICATION

### Check Which Features Were Installed

**Audit Logging:**
- [ ] Check: Does "Users" menu appear in admin area?
- [ ] Check: Does "Audit Logs" link appear in admin area?
- [ ] Check: Does AuditLog model exist in admin interface?

**Reports Dashboard:**
- [ ] Check: Does "Reports" menu item appear in navigation?
- [ ] Check: Can access `http://localhost:8000/reports/`?
- [ ] Check: Do stat cards display data?

**CSV Export:**
- [ ] Check: Do export buttons appear on Reports page?
- [ ] Check: Can click "Export Clients" button?
- [ ] Check: Does download dialog appear?

**Roshe Logo & Branding:**
- [ ] Check: Does header show Roshe branding?
- [ ] Check: Are colors correct (Dark Blue #003366, Yellow #FFD700)?
- [ ] Check: Does logo appear in interface?

**Desktop Shortcut:**
- [ ] Check: Does shortcut exist on Desktop?
- [ ] Check: Does clicking shortcut launch application?
- [ ] Check: Shortcut icon visible on Desktop?

---

## 🛠️ TROUBLESHOOTING

### Common Issues & Solutions

**Issue: "Python not found" error**
- [ ] Verify Python installed: Open Command Prompt, type `python --version`
- [ ] Verify Python in PATH: Reinstall Python with "Add Python to PATH" checked
- [ ] Try: Use `python.exe` or `py` instead of `python`

**Issue: "pip install" fails**
- [ ] Verify internet connection
- [ ] Try: `pip install --upgrade pip`
- [ ] Try: `pip install -r requirements.txt --user`
- [ ] Try: Check for proxy or firewall blocking pip

**Issue: Database migration fails**
- [ ] Delete `db.sqlite3` if exists
- [ ] Delete `logistics/migrations/` folder (except `__init__.py`)
- [ ] Run: `python manage.py makemigrations`
- [ ] Run: `python manage.py migrate`

**Issue: Application won't start**
- [ ] Verify port 8000 is not in use: Close other applications
- [ ] Check Windows Defender or antivirus isn't blocking Python
- [ ] Try: `python manage.py runserver 0.0.0.0:8001`

**Issue: Login page appears but login fails**
- [ ] Verify superuser was created: `python manage.py shell` → `from logistics.models import CustomUser` → `CustomUser.objects.all()`
- [ ] Create new superuser: `python manage.py createsuperuser`
- [ ] Verify username and password are correct

**Issue: CSS/styling looks broken**
- [ ] Run: `python manage.py collectstatic`
- [ ] Clear browser cache: Ctrl+Shift+Delete
- [ ] Try different browser (Chrome, Edge, Firefox)

---

## 📞 SUPPORT

If issues persist:

1. **Check Documentation:**
   - README.md - Overview and quick start
   - INSTALLATION_GUIDE.md - Detailed setup instructions
   - BUILD_GUIDE.md - Building Windows .exe

2. **Contact Roshe Group:**
   - Phone: +256 788 239000 or +8613416137544
   - Email: info@roshegroup.com or roshegroup@gmail.com
   - Address: Plot 13 Mukwano Courts, Buganda Road, floor 2 Room 201–202 I

3. **Check Application Logs:**
   - Check Command Prompt for error messages
   - Screenshots of errors helpful for support

---

## ✨ SUCCESSFUL INSTALLATION INDICATORS

**You have successfully installed the system when:**

✅ Application launches without errors  
✅ Login page appears on startup  
✅ Can log in with superuser account  
✅ Dashboard displays with all widgets  
✅ Navigation menu shows all modules  
✅ Can view all data pages (Clients, Cargo, Transit, Payments, Containers)  
✅ Can create new records (if admin)  
✅ All selected optional features work correctly  
✅ Roshe branding displays (if logo installed)  
✅ Desktop shortcut works (if created)  

---

## 📝 SETUP SUMMARY

| Item | Status | Date |
|------|--------|------|
| Python Installed | ☐ | _____ |
| Project Extracted | ☐ | _____ |
| Setup Wizard Run | ☐ | _____ |
| Database Created | ☐ | _____ |
| Admin Account Created | ☐ | _____ |
| Logo Installed | ☐ | _____ |
| First Launch Successful | ☐ | _____ |
| All Features Verified | ☐ | _____ |

**Installation completed by:** _____________________  
**Date:** _____________________  
**System ready for:** ☐ Single User  ☐ Multiple Users  

---

**© 2025 Roshe Group - All Rights Reserved**  
**Version 1.0.0**
