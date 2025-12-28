"""
Desktop application wrapper for Roshe Group Logistics Portal System
Uses PyWebView to wrap Django application
"""
import os
import sys
import threading
import time
import webview
from pathlib import Path
from django.core.management import execute_from_command_line

# Get the project directory
BASE_DIR = Path(__file__).resolve().parent

def run_django():
    """Run Django development server in a separate thread"""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'roshe_logistics.settings')
    sys.argv = ['manage.py', 'runserver', '127.0.0.1:8000']
    
    try:
        execute_from_command_line(sys.argv)
    except KeyboardInterrupt:
        pass


def create_window():
    """Create PyWebView window"""
    # Start Django server in background thread
    django_thread = threading.Thread(target=run_django, daemon=True)
    django_thread.start()
    
    # Wait for Django server to start
    time.sleep(3)
    
    # Create and show window
    webview.create_window(
        title='Roshe Group Logistics Portal Management System',
        url='http://127.0.0.1:8000/login/',
        width=1400,
        height=900,
        min_size=(1200, 700),
        background_color='#F5F5F5'
    )


if __name__ == '__main__':
    create_window()
