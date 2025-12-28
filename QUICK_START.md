# QUICK START GUIDE - UPDATED INSTALLATION

## Roshe Group Logistics Portal Management System v1.0.1

---

## 🎯 Installation in 3 Steps

### Step 1: Extract Project
Download and extract `Roshe_Logistics_System` folder to your desired location.

### Step 2: Run Interactive Setup
Open Command Prompt in the project folder and run:
```bash
setup_interactive.bat
```

### Step 3: Choose Your Features
Follow the interactive prompts to select which features you want:
- ✓ Audit Logging (track user activity)
- ✓ Reports Dashboard (view statistics)
- ✓ CSV Export (export data to spreadsheet)
- ✓ Roshe Group Logo (professional branding)
- ✓ Desktop Shortcut (quick access)

**That's it!** The system is now ready to use.

---

## 🚀 Launch the Application

### Option 1: Using Quick Start Script
```bash
python run.py
```

### Option 2: Using Desktop Shortcut
Double-click "Roshe Group Logistics Portal" icon on your desktop (if created during setup)

### Option 3: Manual Start
```bash
python desktop_app.py
```

---

## 🔐 First Login

After launching, you'll see the login page.

**Default Admin Account** (created during setup):
- **Username:** The username you created
- **Password:** The password you created

**First-time login:**
1. Enter your admin username
2. Enter your admin password
3. Click "Login"

**What you'll see:**
- Welcome dashboard with statistics
- Navigation menu with all modules
- Roshe Group branding (if installed)

---

## 📊 What You Can Do

### As Superuser (Admin)
✅ Create, edit, and delete records  
✅ Manage user accounts  
✅ View all data  
✅ Export reports to CSV  
✅ View activity logs  
✅ Access system settings  

### Available Modules
1. **Clients** - Store and manage client information
2. **Cargo/Loading** - Track shipments and cargo
3. **Transit** - Monitor vessel movements
4. **Payments** - Manage payments and balances
5. **Containers** - Track container returns
6. **Reports** - View statistics and export data

---

## 📁 Installation Files Reference

| File | Purpose |
|------|---------|
| `setup_interactive.bat` | Interactive setup wizard with feature selection |
| `setup.bat` | Automatic setup (installs all features) |
| `install_logo.py` | Install Roshe Group logo and branding |
| `run.py` | Quick launcher for the application |
| `manage.py` | Django management script |

---

## 📖 Documentation Files

| Document | Use For |
|----------|---------|
| `README.md` | Project overview and features |
| `INSTALLATION_GUIDE.md` | Detailed setup instructions |
| `INSTALLATION_CHECKLIST.md` | Verify successful installation |
| `INSTALLATION_ENHANCEMENTS.md` | New features and options |
| `BUILD_GUIDE.md` | Building Windows .exe file |
| `CONFIG.py` | Configuration reference |

---

## 🔧 System Requirements

- **Windows 10+** (64-bit recommended)
- **Python 3.9+**
- **4GB RAM** (8GB recommended)
- **500MB disk space**
- **Internet** (for initial setup only)

---

## ✅ Verify Installation Success

After first launch, check:
- ✅ Application window opens without errors
- ✅ Login page displays
- ✅ Can log in with admin account
- ✅ Dashboard shows with all widgets
- ✅ Navigation menu visible with all modules
- ✅ Roshe branding visible in header (if installed)
- ✅ Can create new records in Clients, Cargo, etc.

---

## ❓ Troubleshooting

### "Python not found"
- Ensure Python 3.9+ is installed with "Add to PATH" checked
- Verify: Open Command Prompt, type `python --version`

### "Module not found" error
- Run setup again: `setup_interactive.bat`
- Or manually: `pip install -r requirements.txt`

### Application won't start
- Check Windows Defender isn't blocking Python
- Try: `python manage.py runserver 0.0.0.0:8001`
- Port 8000 might be in use by another application

### Can't log in
- Verify you're using the correct username/password
- Create new admin account: `python manage.py createsuperuser`

### Logo/Branding not showing
- Run: `python install_logo.py`
- Run: `python manage.py collectstatic`
- Clear browser cache: `Ctrl + Shift + Delete`

---

## 📞 Support

**Roshe Group Contact:**
- Phone: +256 788 239000 | +8613416137544
- Email: info@roshegroup.com | roshegroup@gmail.com
- Address: Plot 13 Mukwano Courts, Buganda Road, floor 2 Room 201–202 I

---

## 🎯 Next Steps

After successful installation:

1. **Create additional user accounts** (if needed)
   - Admin only: Go to Users page

2. **Import existing data** (if applicable)
   - Add clients and cargo records manually
   - Or use CSV import (coming in future versions)

3. **Customize settings**
   - Configure company information
   - Set up user roles and permissions

4. **Build Windows .exe** (optional)
   - For distribution to other computers
   - See BUILD_GUIDE.md for instructions

5. **Set up backups** (recommended)
   - Backup `db.sqlite3` regularly
   - Store copies in safe location

---

## 💡 Tips

**For Best Performance:**
- Use latest version of Windows
- Ensure antivirus isn't slowing down file access
- Keep Python and packages updated

**For Security:**
- Use strong admin password
- Regularly backup database
- Limit user accounts to authorized personnel
- Review audit logs regularly

**For Data Management:**
- Export CSV reports monthly for backup
- Keep copies of important data
- Don't delete audit logs without reason

---

## 📊 Feature Comparison

| Feature | Core | Audit Log | Reports | CSV Export | Logo |
|---------|------|-----------|---------|-----------|------|
| Client Management | ✅ | — | ✅ | ✅ | — |
| Cargo Management | ✅ | — | ✅ | ✅ | — |
| Transit Tracking | ✅ | — | ✅ | — | — |
| Payment Management | ✅ | — | ✅ | ✅ | — |
| Container Returns | ✅ | — | ✅ | ✅ | — |
| User Activity Log | — | ✅ | — | — | — |
| System Statistics | — | — | ✅ | — | — |
| Data Export | — | — | — | ✅ | — |
| Professional Branding | — | — | — | — | ✅ |

---

## 🎓 Learning Resources

**To learn Django (framework used):**
- Official docs: https://docs.djangoproject.com/
- Django tutorial: https://www.djangoproject.com/start/

**To learn Python:**
- Official docs: https://docs.python.org/
- Python tutorial: https://www.python.org/about/gettingstarted/

**To understand databases:**
- SQLite guide: https://www.sqlite.org/
- Database concepts: https://www.studytonight.com/dbms/

---

## 📝 Version History

**v1.0.1 (Current - December 27, 2025)**
- ✨ Added interactive setup wizard
- ✨ Added feature selection during installation
- ✨ Added logo and branding installation
- ✨ Added installation checklist
- 📝 Updated documentation
- 🐛 Minor bug fixes

**v1.0.0 (Initial Release)**
- Complete offline logistics management system
- Full CRUD operations
- Role-based access control
- CSV export
- Audit logging
- Windows .exe packaging

---

**© 2025 Roshe Group - All Rights Reserved**  
**System Version:** 1.0.1  
**Last Updated:** December 27, 2025
