#!/usr/bin/env python3
"""
Create app icon for FluoroSpot Analysis Tool.
This script generates a simple icon and converts it to .icns format for Mac apps.
"""

import os
import subprocess
from pathlib import Path

def create_simple_icon():
  """Create a simple icon using ImageMagick convert command."""
  print("🎨 Creating app icon...")
  
  # Check if ImageMagick is available
  try:
    subprocess.check_output(["which", "convert"])
  except subprocess.CalledProcessError:
    print("❌ ImageMagick not found. Install with: brew install imagemagick")
    print("   Creating placeholder instead...")
    return create_placeholder_icon()
  
  # Create a simple icon with gradient background and text
  icon_png = "app_icon_1024.png"
  
  # Create base icon
  cmd = [
    "convert", "-size", "1024x1024",
    "gradient:#4A90E2-#357ABD",  # Blue gradient
    "-gravity", "center",
    "-pointsize", "140",
    "-fill", "white",
    "-font", "Arial-Bold",
    "-annotate", "+0-50", "FS",  # FluoroSpot initials
    "-pointsize", "60",
    "-annotate", "+0+50", "Analysis",
    icon_png
  ]
  
  try:
    subprocess.run(cmd, check=True)
    print(f"✅ Base icon created: {icon_png}")
    return convert_to_icns(icon_png)
  except subprocess.CalledProcessError as e:
    print(f"❌ Icon creation failed: {e}")
    return create_placeholder_icon()

def convert_to_icns(png_file):
  """Convert PNG to ICNS format for Mac."""
  print("🔄 Converting to ICNS format...")
  
  iconset_dir = "app_icon.iconset"
  icns_file = "app_icon.icns"
  
  # Create iconset directory
  os.makedirs(iconset_dir, exist_ok=True)
  
  # Generate different icon sizes
  sizes = [
    (16, "icon_16x16.png"),
    (32, "icon_16x16@2x.png"),
    (32, "icon_32x32.png"),
    (64, "icon_32x32@2x.png"),
    (128, "icon_128x128.png"),
    (256, "icon_128x128@2x.png"),
    (256, "icon_256x256.png"),
    (512, "icon_256x256@2x.png"),
    (512, "icon_512x512.png"),
    (1024, "icon_512x512@2x.png")
  ]
  
  try:
    # Generate all icon sizes
    for size, filename in sizes:
      cmd = [
        "convert", png_file,
        "-resize", f"{size}x{size}",
        f"{iconset_dir}/{filename}"
      ]
      subprocess.run(cmd, check=True)
    
    # Convert iconset to icns
    subprocess.run(["iconutil", "-c", "icns", iconset_dir], check=True)
    
    # Clean up
    subprocess.run(["rm", "-rf", iconset_dir], check=True)
    subprocess.run(["rm", png_file], check=True)
    
    print(f"✅ ICNS icon created: {icns_file}")
    return True
    
  except subprocess.CalledProcessError as e:
    print(f"❌ ICNS conversion failed: {e}")
    return False

def create_placeholder_icon():
  """Create a placeholder icon using basic tools."""
  print("📝 Creating placeholder icon...")
  
  # Create a very simple icon using built-in tools
  icns_file = "app_icon.icns"
  
  # Use system icon as template (fallback)
  try:
    subprocess.run([
      "cp", "/System/Library/CoreServices/CoreTypes.bundle/Contents/Resources/GenericApplicationIcon.icns",
      icns_file
    ], check=True)
    print(f"✅ Placeholder icon created: {icns_file}")
    return True
  except subprocess.CalledProcessError:
    print("❌ Could not create placeholder icon")
    return False

def main():
  """Main icon creation process."""
  print("🚀 Starting icon creation...")
  
  # We're already in the build_resources directory when called from fluorospot/
  # Create icon
  success = create_simple_icon()
  
  if success:
    print("✅ App icon created successfully!")
  else:
    print("❌ Failed to create app icon")
    print("   You may need to manually create build_resources/app_icon.icns")

if __name__ == "__main__":
  main()