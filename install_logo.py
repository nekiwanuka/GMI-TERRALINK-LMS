#!/usr/bin/env python
"""
Roshe Group Logo Installer
Installs company logo and branding assets
"""

import os
import shutil
from pathlib import Path

def create_logo_directories():
    """Create necessary directories for logo and branding"""
    base_dir = Path(__file__).parent
    
    directories = [
        base_dir / "logistics" / "static" / "images",
        base_dir / "logistics" / "static" / "css" / "branding",
    ]
    
    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)
        print(f"✓ Created: {directory}")

def create_sample_logo():
    """Create a sample SVG logo for Roshe Group"""
    logo_path = Path(__file__).parent / "logistics" / "static" / "images" / "roshe_logo.svg"
    
    svg_content = '''<svg viewBox="0 0 200 80" xmlns="http://www.w3.org/2000/svg">
  <!-- Background -->
  <rect width="200" height="80" fill="#003366"/>
  
  <!-- Roshe text -->
  <text x="100" y="50" font-family="Arial, sans-serif" font-size="36" font-weight="bold" 
        fill="#FFD700" text-anchor="middle">ROSHE</text>
  
  <!-- Group text -->
  <text x="100" y="70" font-family="Arial, sans-serif" font-size="12" 
        fill="#FFFFFF" text-anchor="middle">GROUP</text>
  
  <!-- Logistics tag -->
  <text x="100" y="12" font-family="Arial, sans-serif" font-size="8" 
        fill="#FFD700" text-anchor="middle">LOGISTICS</text>
</svg>'''
    
    with open(logo_path, 'w') as f:
        f.write(svg_content)
    
    print(f"✓ Created sample logo: {logo_path}")

def create_branding_css():
    """Create branding CSS file"""
    css_path = Path(__file__).parent / "logistics" / "static" / "css" / "branding.css"
    
    css_content = '''/* Roshe Group Branding */

:root {
  --roshe-dark-blue: #003366;
  --roshe-yellow: #FFD700;
  --roshe-white: #FFFFFF;
  --roshe-light-gray: #F5F5F5;
}

/* Logo styling */
.roshe-logo {
  max-width: 200px;
  height: auto;
  margin: 10px 0;
}

.navbar-brand {
  color: var(--roshe-yellow) !important;
  font-weight: bold;
  font-size: 18px;
}

.navbar-brand span {
  color: var(--roshe-dark-blue);
}

/* Primary button - Roshe colors */
.btn-roshe {
  background-color: var(--roshe-dark-blue);
  border-color: var(--roshe-dark-blue);
  color: white;
}

.btn-roshe:hover {
  background-color: #001f4d;
  border-color: #001f4d;
  color: var(--roshe-yellow);
}

/* Accent button */
.btn-roshe-accent {
  background-color: var(--roshe-yellow);
  border-color: var(--roshe-yellow);
  color: var(--roshe-dark-blue);
}

.btn-roshe-accent:hover {
  background-color: #e6c200;
  border-color: #e6c200;
  color: var(--roshe-dark-blue);
}

/* Header branding */
.roshe-header {
  background: linear-gradient(135deg, var(--roshe-dark-blue) 0%, var(--roshe-dark-blue) 85%, var(--roshe-yellow) 100%);
  color: white;
  padding: 20px;
  margin-bottom: 20px;
  border-radius: 5px;
}

.roshe-header h1 {
  color: var(--roshe-yellow);
  margin: 0;
}

.roshe-header p {
  color: var(--roshe-light-gray);
  margin: 5px 0 0 0;
}

/* Footer branding */
.roshe-footer {
  background-color: var(--roshe-dark-blue);
  color: white;
  padding: 20px;
  margin-top: 40px;
  text-align: center;
  border-top: 3px solid var(--roshe-yellow);
}

.roshe-footer a {
  color: var(--roshe-yellow);
  text-decoration: none;
}

.roshe-footer a:hover {
  text-decoration: underline;
}

/* Dashboard cards */
.roshe-card {
  border: 2px solid var(--roshe-dark-blue);
  border-left: 5px solid var(--roshe-yellow);
}

.roshe-card .card-header {
  background-color: var(--roshe-dark-blue);
  color: white;
}

/* Status badges with Roshe colors */
.badge-roshe-active {
  background-color: var(--roshe-dark-blue);
}

.badge-roshe-pending {
  background-color: var(--roshe-yellow);
  color: var(--roshe-dark-blue);
}

/* Sidebar with branding */
.sidebar {
  background-color: var(--roshe-dark-blue);
}

.sidebar a {
  color: white;
}

.sidebar a:hover {
  background-color: #001f4d;
  color: var(--roshe-yellow);
}

.sidebar .active {
  background-color: var(--roshe-yellow);
  color: var(--roshe-dark-blue);
}
'''
    
    with open(css_path, 'w') as f:
        f.write(css_content)
    
    print(f"✓ Created branding CSS: {css_path}")

def main():
    """Main installation function"""
    print("\n" + "="*50)
    print("ROSHE GROUP LOGO & BRANDING INSTALLER")
    print("="*50 + "\n")
    
    try:
        print("Step 1: Creating directories...")
        create_logo_directories()
        print()
        
        print("Step 2: Creating sample logo...")
        create_sample_logo()
        print()
        
        print("Step 3: Creating branding CSS...")
        create_branding_css()
        print()
        
        print("="*50)
        print("✓ INSTALLATION COMPLETE")
        print("="*50)
        print("\nNext steps:")
        print("1. Replace sample logo with official Roshe Group logo")
        print("   Location: logistics/static/images/roshe_logo.svg")
        print("2. Run the application: python run.py")
        print("3. You should see Roshe branding throughout the UI")
        print()
        print("Official logo download:")
        print("  Visit: https://roshegroup.com/media/logo.png")
        print("  Or contact: info@roshegroup.com")
        print()
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())
