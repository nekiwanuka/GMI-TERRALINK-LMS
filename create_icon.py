#!/usr/bin/env python
"""
Create a simple ICO file for the application
"""
from PIL import Image, ImageDraw

# Create a simple icon - dark blue square with yellow box
img = Image.new('RGB', (256, 256), color='#1E1A23')
draw = ImageDraw.Draw(img)

# Draw yellow box
draw.rectangle([40, 40, 216, 216], fill='#F4C21F', outline='#1E1A23', width=3)

# Draw inner dark blue box
draw.rectangle([70, 70, 186, 186], fill='#1E1A23', outline='#F4C21F', width=2)

# Save as ICO
img.save('gmi_terralink_icon.ico')
print("✓ Icon created: gmi_terralink_icon.ico")
