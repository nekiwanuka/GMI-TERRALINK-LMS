"""
Quick Start Script for Roshe Group Logistics Portal System
Run this script to quickly start the application after first-time setup
"""
import os
import sys
import subprocess

def main():
    print("\n" + "="*60)
    print("Roshe Group Logistics Portal Management System - Quick Start")
    print("="*60 + "\n")
    
    # Check if database exists
    if not os.path.exists('db.sqlite3'):
        print("Database not found. Running initial setup...")
        print("\nRunning migrations...")
        subprocess.run([sys.executable, 'manage.py', 'migrate'])
        
        print("\nCreating superuser account...")
        subprocess.run([sys.executable, 'manage.py', 'createsuperuser'])
    
    print("\n" + "="*60)
    print("Starting Roshe Group Logistics Portal Application...")
    print("="*60 + "\n")
    
    # Run desktop app
    subprocess.run([sys.executable, 'desktop_app.py'])

if __name__ == '__main__':
    main()
