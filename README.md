# GMI TERRALINK Logistics Portal Management System

**A Complete Offline Desktop Application for GMI TERRALINK**

## 📋 Overview

GMI TERRALINK Logistics Portal is a professional, offline-capable desktop logistics management system built for GMI TERRALINK. It provides comprehensive functionality for managing:

- **Clients** - Store and manage client information
- **Cargo/Loading** - Track shipments and cargo movements
- **Transit Management** - Monitor vessel movements and delivery status
- **Payments** - Manage payments and outstanding balances
- **Container Returns** - Track container returns and conditions
- **Proforma & Final Invoices** - Issue, track and finalise invoices to clients
- **Purchase Orders & Sourcing** - Manage supplier sourcing, POs and final supplier invoices
- **Fulfillment & Shipment Legs** - Multi-leg shipment workflow with cargo items
- **Billing Charges & Invoices** - Event-driven operational billing per shipment
- **Commissions** - Director / System Admin restricted ledger of commissions earned per client
- **Reports** - Executive dashboard with revenue, profit, commissions and CSV exports
- **Audit Trails** - Complete audit logging for compliance

> Need a release-level snapshot? See the [Completion Report Highlights](PROJECT_SUMMARY.md#completion-report-highlights) for validated metrics and delivery status.

## 🎯 Features

### User Roles

- **System Admin (`ADMIN`) / Superuser**: Full access including user management, audit logs, executive reports and the commission ledger.
- **Director (`DIRECTOR`)**: Executive access including reports dashboard and commission ledger; cannot manage users.
- **Office Admin (`OFFICE_ADMIN`)**: Day-to-day operations across clients, shipments, invoices and POs.
- **Finance (`FINANCE`)**: Invoices, payments, billing charges, receipts and finance-side reports.
- **Procurement (`PROCUREMENT`)**: Suppliers, sourcing and purchase orders.

> Commission entries are visible **only** to System Admin / Director / Superuser. All other roles cannot see the menu, the ledger, or commission totals on the reports dashboard.

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
gmi_terralink_System/
├── gmi_terralink/           # Django project configuration
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
├── gmi_terralink.spec     # PyInstaller configuration
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
- Install GMI TERRALINK logo & branding
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
- 🎨 GMI TERRALINK Logo & Branding
- 🔗 Desktop Shortcut

## 🖥️ Running the Application

### Quick Launch

```bash
python run.py
```

### Or use the desktop shortcut (if created during setup)

Double-click "GMI TERRALINK Logistics Portal" shortcut on your desktop

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
   pyinstaller gmi_terralink.spec
   ```

3. **Find your .exe:**
   The executable will be in `dist\GMITerralink.exe`

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
- **Executive Reports Dashboard**: Total revenue, outstanding balance, profit estimate, top clients, supplier mix, status distribution and **commission earned by currency**

All reports can be exported as CSV for use in Excel or other tools.

### Commissions Module (Director / Admin Only)

The Commission ledger lets the Director or System Admin record the commissions GMI Terralink earns per client engagement.

**Workflow:**

1. Open **Executive → Commissions** in the sidebar (only visible to Director / System Admin / Superuser).
2. Click **Record commission**.
3. Pick the client, enter the commission **amount**, choose **currency** (USD / UGX / CNY / EUR / GBP / KES) and the **date** the commission was earned.
4. Add optional **notes** for context (e.g. associated shipment, deal reference).
5. Save. The entry is added to the ledger and aggregated into per-currency totals.

**Where it shows up:**

- `/commissions/` — full ledger with filters (client, currency), per-currency total chips, edit and delete actions.
- `/reports/` — dashboard panel **"Commission earned"** showing per-currency totals with a deep-link back to the ledger.
- All create / update / delete actions are written to the audit log.

## 🔒 Security & Permissions

### Role-Based Access Control

**System Admin / Superuser Can:**

- ✅ Create / edit / delete all records
- ✅ Create and manage users
- ✅ View audit logs and executive reports
- ✅ Record and view commissions
- ✅ Access Django admin panel

**Director Can:**

- ✅ View all operational records
- ✅ View executive reports dashboard
- ✅ Record and view commissions
- ❌ Manage users (read-only of executive data)

**Office Admin Can:**

- ✅ Create / edit clients, shipments, fulfillment, invoices and POs
- ❌ See commissions or executive-only reports

**Finance Can:**

- ✅ Manage invoices, billing charges, payments and receipts
- ❌ See commissions ledger

**Procurement Can:**

- ✅ Manage suppliers, sourcing requests and purchase orders
- ❌ See commissions ledger or finance-restricted views

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

### Commission _(Director / Admin only)_

- `client` (FK → Client, PROTECT)
- `amount` (Decimal 14,2, > 0)
- `currency` (USD / UGX / CNY / EUR / GBP / KES)
- `date` (date earned)
- `notes` (optional)
- `created_by` (FK → CustomUser)
- `created_at`, `updated_at`

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

**GMI TERRALINK Contact Information:**

- Phone: +256 788 239000 | +8613416137544
- Email: gmiterralinkinfo@gmail.com
- Address: Plot 13 Mukwano Courts, Buganda Road, floor 2 Room 201–202 I

## 📄 License & Copyright

© 2025 GMI TERRALINK. All Rights Reserved.

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
- [ ] Build executable: `pyinstaller gmi_terralink.spec`
- [ ] Test .exe file on target computers
- [ ] Distribute to users

## 🔄 Version History

**Version 1.1.0** - April 2026

- Added **Commission ledger** module (Director / System Admin only)
  - CRUD with per-currency aggregation and audit logging
  - Surfaced as a panel on the executive Reports dashboard
  - Sidebar link gated behind `is_superuser` or role in `ADMIN, DIRECTOR`
- Refreshed role / permission documentation to reflect ADMIN / DIRECTOR / OFFICE_ADMIN / FINANCE / PROCUREMENT roles
- Document header strip refined across Final Invoice, Proforma and Purchase Order with iconified address line

**Version 1.0.0** - December 2025

- Initial release
- Complete offline functionality
- All core modules implemented
- CSV export capability
- Role-based access control
- Audit logging system

# GMI TERRALINK-group_system
