#!/usr/bin/env python
"""
Create a simple ICO file for the application
"""
from PIL import Image, ImageDraw

# Create a simple icon - dark blue square with yellow box
img = Image.new('RGB', (256, 256), color='#003366')
draw = ImageDraw.Draw(img)

# Draw yellow box
draw.rectangle([40, 40, 216, 216], fill='#FFD700', outline='#003366', width=3)

# Draw inner dark blue box
draw.rectangle([70, 70, 186, 186], fill='#003366', outline='#FFD700', width=2)

# Save as ICO
img.save('roshe_icon.ico')
print("✓ Icon created: roshe_icon.ico")
