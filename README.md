# Roshe Group Logistics Portal Management System

**A Complete Offline Desktop Application for Roshe Group**

## 📋 Overview

Roshe Group Logistics Portal is a professional, offline-capable desktop logistics management system built for Roshe Group. It provides comprehensive functionality for managing:

- **Clients** - Store and manage client information
- **Cargo/Loading** - Track shipments and cargo movements
- **Transit Management** - Monitor vessel movements and delivery status
- **Payments** - Manage payments and outstanding balances
- **Container Returns** - Track container returns and conditions
- **Reports** - Generate and export comprehensive reports to CSV
- **Audit Trails** - Complete audit logging for compliance

## 🎯 Features

### User Roles
- **Superuser (Admin)**: Full access - Create, edit, delete records, manage users, view all data
- **Data Entry User**: Limited access - Can only add records and view existing data

### Key Capabilities
✅ **Fully Offline** - Works without internet connection  
✅ **SQLite Database** - Local database for data persistence  
✅ **CSV Export** - Export reports for external analysis  
✅ **Role-Based Access Control** - Secure user permissions  
✅ **Audit Logging** - Complete activity tracking  
✅ **Professional UI** - Bootstrap-based responsive design  
✅ **Desktop Application** - Runs as standalone Windows .exe  

## 🏗️ Project Structure

```
Roshe_Logistics_System/
├── roshe_logistics/           # Django project configuration
│   ├── settings.py           # Project settings
│   ├── urls.py              # URL routing
│   ├── wsgi.py              # WSGI configuration
│   └── asgi.py              # ASGI configuration
│
├── logistics/               # Main Django application
│   ├── models.py            # Database models
│   ├── views.py             # View logic and CRUD operations
│   ├── forms.py             # Django forms
│   ├── admin.py             # Admin interface
│   ├── apps.py              # App configuration
│   ├── urls.py              # App URL patterns
│   │
│   ├── templates/logistics/
│   │   ├── base.html        # Base template with navigation
│   │   ├── login.html       # Login page
│   │   ├── dashboard.html   # Main dashboard
│   │   ├── clients/         # Client management templates
│   │   ├── loadings/        # Cargo management templates
│   │   ├── transits/        # Transit management templates
│   │   ├── payments/        # Payment templates
│   │   ├── containers/      # Container return templates
│   │   ├── reports/         # Reports dashboard
│   │   └── audit_logs.html  # Audit log viewer
│   │
│   └── static/
│       ├── css/             # Stylesheets
│       └── js/              # JavaScript files
│
├── manage.py                 # Django management script
├── desktop_app.py           # PyWebView desktop wrapper
├── roshe_logistics.spec     # PyInstaller configuration
├── requirements.txt         # Python dependencies
├── db.sqlite3              # SQLite database (auto-created)
├── README.md               # This file
└── .gitignore              # Git ignore patterns
```

## 🚀 Installation & Setup

### Prerequisites
- **Windows 10 or higher**
- **Python 3.9+** ([Download](https://www.python.org/downloads/))
- **pip** (comes with Python)

### Quick Start (Recommended)

**Option 1: Interactive Setup with Feature Selection**
```bash
setup_interactive.bat
```

This interactive wizard allows you to:
- Choose which features to install
- Select optional modules
- Install Roshe Group logo & branding
- Create desktop shortcut
- Create admin account

**Option 2: Automatic Setup (All Features)**
```bash
setup.bat
```

### Manual Installation

**Step 1: Install Dependencies**
```bash
pip install -r requirements.txt
```

**Step 2: Install Optional Logo & Branding**
```bash
python install_logo.py
```

**Step 3: Initialize Database**
```bash
python manage.py migrate
```

**Step 4: Create Admin Account**
```bash
python manage.py createsuperuser
```

### Feature Selection Details

**Core Features (Always Installed)**
- ✅ Client Management
- ✅ Cargo/Loading Management
- ✅ Transit Management
- ✅ Payment Management
- ✅ Container Returns

**Optional Features (Choose During Setup)**
- 📊 Audit Logging & Activity Tracking
- 📈 Reports Dashboard
- 📄 CSV Export
- 🎨 Roshe Group Logo & Branding
- 🔗 Desktop Shortcut

## 🖥️ Running the Application

### Quick Launch
```bash
python run.py
```

### Or use the desktop shortcut (if created during setup)
Double-click "Roshe Group Logistics Portal" shortcut on your desktop

### Development Mode
```bash
python desktop_app.py
```

This launches the application in a PyWebView window. The application runs on `http://127.0.0.1:8000` and opens automatically.

### Option B: Web Mode (Browser)

```bash
python manage.py runserver
```

Then open your browser and navigate to: `http://127.0.0.1:8000/login/`

### Login
- **Username**: The superuser username you created
- **Password**: The superuser password you created

## 📦 Building Windows .exe

### Prerequisites for Building
```bash
pip install pyinstaller
```

### Build Steps

1. **Prepare the build environment:**
   ```bash
   python manage.py collectstatic --noinput
   ```

2. **Create the executable:**
   ```bash
   pyinstaller roshe_logistics.spec
   ```

3. **Find your .exe:**
   The executable will be in `dist/RosheLogistics.exe`

4. **Optional: Create installer using NSIS**
   - Install NSIS from https://nsis.sourceforge.io/
   - Create a .nsi script for a full installer

### Distribution

The built `.exe` can be:
- Shared directly with users
- Run on any Windows 10+ computer
- Installed on multiple computers
- Operates completely offline after initial setup

## 📊 Module Descriptions

### Client Management
- Add and manage client information
- Track contact persons and addresses
- View all associated shipments
- Add/edit/delete client records (admin only)

### Cargo/Loading Management
- Create loading records with cargo details
- Track container numbers and weights
- Manage origin and destination information
- Link cargo to clients

### Transit Management
- Record vessel information
- Track boarding dates and ETAs
- Monitor shipment status (Awaiting, In Transit, Arrived)
- Update transit information

### Payment Management
- Record payment details
- Track amounts charged and paid
- Calculate outstanding balances (automatic)
- Export payment reports
- Filter by payment status

### Container Returns
- Record container returns
- Track container condition (Good, Damaged, Missing)
- Monitor return status
- Manage return remarks

### Reports & Exports
- **Client Report**: All clients and their details
- **Shipment Report**: Complete cargo information
- **Payment Report**: Payment summaries and balances
- **Container Report**: Container return history

All reports can be exported as CSV for use in Excel or other tools.

## 🔒 Security & Permissions

### Role-Based Access Control

**Superuser Can:**
- ✅ Create all records
- ✅ Edit all records
- ✅ Delete records
- ✅ Create and manage users
- ✅ View audit logs
- ✅ Access admin panel

**Data Entry User Can:**
- ✅ View all records
- ✅ Add new records
- ❌ Edit records (except in audit)
- ❌ Delete records
- ❌ Manage users
- ❌ Access audit logs

### Audit Logging
Every action (create, update, delete) is logged with:
- User who performed the action
- Timestamp
- Record type and ID
- Action type
- Changes made

Access via: **Dashboard → Audit Logs** (Admin Only)

## 📝 Database Models

### CustomUser
- Username, email, password
- First/last name, phone
- Role (superuser/data_entry)
- Created timestamp

### Client
- Client ID (unique)
- Name, contact person
- Phone, address
- Date registered
- Remarks

### Loading
- Loading ID (unique)
- Client (foreign key)
- Loading date, item description
- Weight (KG), container number
- Origin, destination

### Transit
- Loading (one-to-one)
- Vessel name
- Boarding date, ETA Kampala
- Status (awaiting/in_transit/arrived)
- Remarks

### Payment
- Loading (one-to-one)
- Amount charged, amount paid
- Balance (calculated automatically)
- Payment date, payment method
- Receipt number

### ContainerReturn
- Container number
- Loading (foreign key)
- Return date, condition
- Status, remarks

### AuditLog
- User, model type, action
- Object ID, object string
- Changes (JSON)
- Timestamp

## 🛠️ Troubleshooting

### Issue: Database locked error
**Solution:** Close all instances of the application and try again

### Issue: Port 8000 already in use
**Solution:** Change the port in desktop_app.py:
```python
sys.argv = ['manage.py', 'runserver', '127.0.0.1:8001']
```

### Issue: Missing migrations
**Solution:** Run `python manage.py migrate`

### Issue: Static files not loading
**Solution:** Run `python manage.py collectstatic --noinput`

## 📧 Support

**Roshe Group Contact Information:**
- Phone: +256 788 239000 | +8613416137544
- Email: info@roshegroup.com | roshegroup@gmail.com
- Address: Plot 13 Mukwano Courts, Buganda Road, floor 2 Room 201–202 I

## 📄 License & Copyright

© 2025 Roshe Group. All Rights Reserved.

This system is proprietary and confidential. Unauthorized distribution is prohibited.

## 🎨 Brand Colors

- **Primary:** Dark Blue (#003366)
- **Secondary:** Yellow (#FFD700)
- **Background:** Light Gray (#F5F5F5)

## ✅ Checklist for Deployment

- [ ] Install Python 3.9+
- [ ] Install dependencies: `pip install -r requirements.txt`
- [ ] Run migrations: `python manage.py migrate`
- [ ] Create superuser: `python manage.py createsuperuser`
- [ ] Test application: `python desktop_app.py`
- [ ] Build executable: `pyinstaller roshe_logistics.spec`
- [ ] Test .exe file on target computers
- [ ] Distribute to users

## 🔄 Version History

**Version 1.0.0** - December 2025
- Initial release
- Complete offline functionality
- All core modules implemented
- CSV export capability
- Role-based access control
- Audit logging system
# roshe-group_system
