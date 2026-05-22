#!/usr/bin/env python
"""
GMI TERRALINK Logo Installer
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
    """Create a sample SVG logo for GMI TERRALINK"""
    logo_path = (
        Path(__file__).parent / "logistics" / "static" / "images" / "gmi_logo.svg"
    )

    svg_content = """<svg viewBox="0 0 200 80" xmlns="http://www.w3.org/2000/svg">
  <!-- Background -->
  <rect width="200" height="80" fill="#1E1A23"/>
  
  <!-- GMI text -->
  <text x="100" y="50" font-family="Arial, sans-serif" font-size="36" font-weight="bold" 
        fill="#F4C21F" text-anchor="middle">GMI</text>
  
    <!-- TERRALINK text -->
  <text x="100" y="70" font-family="Arial, sans-serif" font-size="12" 
      fill="#FFFFFF" text-anchor="middle">TERRALINK</text>
  
  <!-- Logistics tag -->
  <text x="100" y="12" font-family="Arial, sans-serif" font-size="8" 
        fill="#F4C21F" text-anchor="middle">TERRALINK</text>
</svg>"""

    with open(logo_path, "w") as f:
        f.write(svg_content)

    print(f"✓ Created sample logo: {logo_path}")


def create_branding_css():
    """Create branding CSS file"""
    css_path = Path(__file__).parent / "logistics" / "static" / "css" / "branding.css"

    css_content = """/* GMI TERRALINK Branding */

:root {
  --gmi-dark-blue: #1E1A23;
  --gmi-yellow: #F4C21F;
  --gmi-white: #FFFFFF;
  --gmi-light-gray: #F4F4F1;
}

/* Logo styling */
.gmi-logo {
  max-width: 200px;
  height: auto;
  margin: 10px 0;
}

.navbar-brand {
  color: var(--gmi-yellow) !important;
  font-weight: bold;
  font-size: 18px;
}

.navbar-brand span {
  color: var(--gmi-dark-blue);
}

/* Primary button - GMI TERRALINK colors */
.btn-gmi {
  background-color: var(--gmi-dark-blue);
  border-color: var(--gmi-dark-blue);
  color: white;
}

.btn-gmi:hover {
  background-color: #141118;
  border-color: #141118;
  color: var(--gmi-yellow);
}

/* Accent button */
.btn-gmi-accent {
  background-color: var(--gmi-yellow);
  border-color: var(--gmi-yellow);
  color: var(--gmi-dark-blue);
}

.btn-gmi-accent:hover {
  background-color: #dfaf19;
  border-color: #dfaf19;
  color: var(--gmi-dark-blue);
}

/* Header branding */
.gmi-header {
  background: linear-gradient(135deg, var(--gmi-dark-blue) 0%, var(--gmi-dark-blue) 85%, var(--gmi-yellow) 100%);
  color: white;
  padding: 20px;
  margin-bottom: 20px;
  border-radius: 5px;
}

.gmi-header h1 {
  color: var(--gmi-yellow);
  margin: 0;
}

.gmi-header p {
  color: var(--gmi-light-gray);
  margin: 5px 0 0 0;
}

/* Footer branding */
.gmi-footer {
  background-color: var(--gmi-dark-blue);
  color: white;
  padding: 20px;
  margin-top: 40px;
  text-align: center;
  border-top: 3px solid var(--gmi-yellow);
}

.gmi-footer a {
  color: var(--gmi-yellow);
  text-decoration: none;
}

.gmi-footer a:hover {
  text-decoration: underline;
}

/* Dashboard cards */
.gmi-card {
  border: 2px solid var(--gmi-dark-blue);
  border-left: 5px solid var(--gmi-yellow);
}

.gmi-card .card-header {
  background-color: var(--gmi-dark-blue);
  color: white;
}

/* Status badges with GMI TERRALINK colors */
.badge-gmi-active {
  background-color: var(--gmi-dark-blue);
}

.badge-gmi-pending {
  background-color: var(--gmi-yellow);
  color: var(--gmi-dark-blue);
}

/* Sidebar with branding */
.sidebar {
  background-color: var(--gmi-dark-blue);
}

.sidebar a {
  color: white;
}

.sidebar a:hover {
  background-color: #141118;
  color: var(--gmi-yellow);
}

.sidebar .active {
  background-color: var(--gmi-yellow);
  color: var(--gmi-dark-blue);
}
"""

    with open(css_path, "w") as f:
        f.write(css_content)

    print(f"✓ Created branding CSS: {css_path}")


def main():
    """Main installation function"""
    print("\n" + "=" * 50)
    print("GMI TERRALINK LOGO & BRANDING INSTALLER")
    print("=" * 50 + "\n")

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

        print("=" * 50)
        print("✓ INSTALLATION COMPLETE")
        print("=" * 50)
        print("\nNext steps:")
        print("1. Replace sample logo with official GMI TERRALINK logo")
        print("   Location: logistics/static/images/gmi_logo.svg")
        print("2. Run the application: python run.py")
        print("3. You should see GMI TERRALINK branding throughout the UI")
        print()
        print("Official logo download:")
        print("  Visit: https://gmiterralink.com")
        print("  Or contact: info@gmiterralink.com")
        print()

    except Exception as e:
        print(f"\n✗ Error: {e}")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
