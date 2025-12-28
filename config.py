"""
Roshe Group Logistics Portal Management System
Complete Project Configuration and Initialization
"""

PROJECT_INFO = {
    'name': 'Roshe Group Logistics Portal Management System',
    'company': 'Roshe Group',
    'version': '1.0.0',
    'release_date': 'December 2025',
    'license': 'Proprietary - All Rights Reserved',
}

COMPANY_INFO = {
    'name': 'Roshe Group',
    'phone': ['+256 788 239000', '+8613416137544'],
    'email': ['info@roshegroup.com', 'roshegroup@gmail.com'],
    'address': 'Plot 13 Mukwano Courts, Buganda Road, floor 2 Room 201–202 I',
    'country': 'Uganda',
}

BRAND_COLORS = {
    'primary': '#003366',      # Dark Blue
    'secondary': '#FFD700',    # Yellow
    'background': '#F5F5F5',   # Light Gray
    'white': '#FFFFFF',
    'dark': '#000000',
}

SYSTEM_MODULES = {
    'Client Management': {
        'description': 'Store and manage client information',
        'features': [
            'Add/Edit/Delete clients',
            'Track contact information',
            'View associated shipments',
            'Manage remarks and notes',
        ]
    },
    'Cargo/Loading Management': {
        'description': 'Track shipments and cargo movements',
        'features': [
            'Create loading records',
            'Track container numbers',
            'Monitor weight and destination',
            'Link to clients',
        ]
    },
    'Transit Management': {
        'description': 'Monitor vessel movements and delivery status',
        'features': [
            'Record vessel information',
            'Track boarding dates and ETAs',
            'Update shipment status',
            'Monitor routes',
        ]
    },
    'Payment Management': {
        'description': 'Manage payments and outstanding balances',
        'features': [
            'Record payment details',
            'Calculate outstanding balances',
            'Track payment methods',
            'Generate payment reports',
        ]
    },
    'Container Return Management': {
        'description': 'Track container returns and conditions',
        'features': [
            'Record container returns',
            'Track condition status',
            'Manage return remarks',
            'Monitor return timeline',
        ]
    },
    'Reports & Analytics': {
        'description': 'Generate and export comprehensive reports',
        'features': [
            'Client reports',
            'Shipment reports',
            'Payment reports',
            'CSV export functionality',
            'Dashboard analytics',
        ]
    },
    'Audit & Compliance': {
        'description': 'Track all system activities and changes',
        'features': [
            'Complete audit logging',
            'User activity tracking',
            'Data change history',
            'Compliance reporting',
        ]
    },
}

USER_ROLES = {
    'Superuser (Admin)': {
        'permissions': [
            'Create all records',
            'Edit all records',
            'Delete records',
            'Create and manage users',
            'View audit logs',
            'Access admin panel',
        ]
    },
    'Data Entry User': {
        'permissions': [
            'Add new records',
            'View all records',
            '❌ Cannot edit',
            '❌ Cannot delete',
            '❌ Cannot manage users',
        ]
    },
}

SYSTEM_REQUIREMENTS = {
    'Operating System': 'Windows 10 or higher (64-bit)',
    'RAM': '4 GB minimum (8 GB recommended)',
    'Disk Space': '500 MB for installation',
    'Python Version': '3.9 or higher',
    'Internet': 'Not required after setup',
}

TECHNOLOGY_STACK = {
    'Backend Framework': 'Django 4.2.7',
    'Database': 'SQLite3',
    'Frontend': 'HTML5, Bootstrap 5, CSS3',
    'Desktop Wrapper': 'PyWebView 4.4',
    'Packaging': 'PyInstaller 6.1.0',
    'Server': 'Django Development Server',
    'Version Control': 'Git',
}

INSTALLATION_STEPS = [
    '1. Install Python 3.9+ with pip',
    '2. Extract project files',
    '3. Run setup.bat (automatic setup)',
    '4. Create superuser account',
    '5. Run application with run.py',
    '6. Login and start using',
]

BUILD_STEPS = [
    '1. Prepare environment: setup.bat',
    '2. Collect static files',
    '3. Run build.bat',
    '4. Find executable in dist/ folder',
    '5. Test on different computers',
    '6. Distribute RosheLogistics.exe',
]

DEPLOYMENT_OPTIONS = {
    'Standalone .exe': {
        'best_for': 'Individual computers or small teams',
        'complexity': 'Simple',
        'data_sync': 'None (separate databases)',
    },
    'Network Shared Database': {
        'best_for': 'Teams needing shared data',
        'complexity': 'Medium',
        'data_sync': 'Real-time (shared SQLite)',
    },
    'Professional Installer': {
        'best_for': 'Enterprise deployment',
        'complexity': 'Advanced',
        'data_sync': 'With network database',
    },
}

FILE_STRUCTURE = """
Roshe_Logistics_System/
│
├── roshe_logistics/
│   ├── __init__.py
│   ├── settings.py                  [Django configuration]
│   ├── urls.py                      [URL routing]
│   ├── wsgi.py                      [WSGI server]
│   └── asgi.py                      [ASGI server]
│
├── logistics/
│   ├── migrations/
│   ├── templates/logistics/
│   │   ├── base.html               [Base template]
│   │   ├── login.html
│   │   ├── dashboard.html
│   │   ├── register.html
│   │   ├── audit_logs.html
│   │   ├── clients/                [Client templates]
│   │   ├── loadings/               [Cargo templates]
│   │   ├── transits/               [Transit templates]
│   │   ├── payments/               [Payment templates]
│   │   ├── containers/             [Container templates]
│   │   └── reports/                [Report templates]
│   │
│   ├── static/
│   │   ├── css/
│   │   └── js/
│   │
│   ├── __init__.py
│   ├── admin.py                     [Django admin config]
│   ├── apps.py                      [App configuration]
│   ├── models.py                    [Database models]
│   ├── views.py                     [View logic and CRUD]
│   ├── forms.py                     [Django forms]
│   ├── urls.py                      [App URL patterns]
│   └── tests.py                     [Test cases]
│
├── database/                        [Database backups]
├── exports/                         [CSV exports]
├── users/                           [User documentation]
│
├── manage.py                        [Django management]
├── desktop_app.py                   [PyWebView wrapper]
├── run.py                           [Quick start script]
├── roshe_logistics.spec             [PyInstaller config]
│
├── setup.bat                        [Windows setup script]
├── setup.sh                         [Linux/Mac setup script]
├── build.bat                        [Windows build script]
│
├── requirements.txt                 [Python dependencies]
├── README.md                        [Main documentation]
├── INSTALLATION_GUIDE.md            [Installation steps]
├── BUILD_GUIDE.md                   [Build & deployment guide]
├── config.py                        [Configuration]
│
└── db.sqlite3                       [SQLite database]
"""

QUICK_START = """
QUICK START GUIDE
=================

1. SETUP (One-time only):
   $ setup.bat
   
2. RUN APPLICATION:
   $ python run.py
   
3. LOGIN:
   Username: (created during setup)
   Password: (created during setup)
   
4. BUILD EXECUTABLE (optional):
   $ build.bat
   
5. FIND EXECUTABLE:
   dist/RosheLogistics.exe
"""

FEATURES_SUMMARY = """
SYSTEM FEATURES SUMMARY
=======================

✅ FULLY OFFLINE
   - No internet required
   - Works in areas with no connectivity
   - Local data storage

✅ SECURE
   - Role-based access control
   - User authentication
   - Complete audit trails
   - Password protection

✅ PROFESSIONAL
   - Clean, modern UI
   - Roshe Group branding
   - Professional reports
   - Error handling

✅ FLEXIBLE
   - Runs on Windows
   - Distributable as .exe
   - Shareable database
   - Network deployment

✅ RELIABLE
   - SQLite database
   - Automatic backups
   - Error recovery
   - Data validation

✅ SCALABLE
   - Supports multiple users
   - Expandable modules
   - Additional features easy to add
   - Network-ready
"""

NEXT_STEPS = """
AFTER INSTALLATION
==================

1. Create user accounts for team members
2. Set up client records in the system
3. Import initial data (if available)
4. Train staff on system usage
5. Set up regular database backups
6. Configure export schedules
7. Monitor system performance
8. Plan future enhancements

SUPPORT
=======
Contact Roshe Group:
- Phone: +256 788 239000 | +8613416137544
- Email: info@roshegroup.com | roshegroup@gmail.com
- Address: Plot 13 Mukwano Courts, Buganda Road, floor 2 Room 201–202 I
"""

if __name__ == '__main__':
    print(QUICK_START)
    print(FEATURES_SUMMARY)
    print(NEXT_STEPS)
