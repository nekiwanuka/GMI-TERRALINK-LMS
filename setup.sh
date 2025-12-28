#!/bin/bash
# Setup script for Roshe Group Logistics Portal System

echo "================================================"
echo "Roshe Group Logistics Portal Management System Setup"
echo "================================================"
echo ""

# Check if Python is installed
echo "Checking Python installation..."
python --version
if [ $? -ne 0 ]; then
    echo "ERROR: Python is not installed or not in PATH"
    exit 1
fi

# Install dependencies
echo ""
echo "Installing dependencies..."
pip install -r requirements.txt
if [ $? -ne 0 ]; then
    echo "ERROR: Failed to install dependencies"
    exit 1
fi

# Run migrations
echo ""
echo "Running database migrations..."
python manage.py migrate
if [ $? -ne 0 ]; then
    echo "ERROR: Failed to run migrations"
    exit 1
fi

# Create superuser
echo ""
echo "Creating superuser account..."
python manage.py createsuperuser

echo ""
echo "================================================"
echo "Setup Complete!"
echo "================================================"
echo ""
echo "To start the application, run:"
echo "  python desktop_app.py"
echo ""
echo "For development mode (browser):"
echo "  python manage.py runserver"
echo ""
