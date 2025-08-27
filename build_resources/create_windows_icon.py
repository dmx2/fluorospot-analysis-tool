#!/usr/bin/env python3
"""
Create Windows icon for FluoroSpot Analysis Tool.
This script generates a simple icon and converts it to .ico format for Windows apps.
"""

import os
import subprocess
import sys
from pathlib import Path

def create_simple_icon():
    """Create a simple icon using ImageMagick or Pillow."""
    print("🎨 Creating Windows app icon...")
    
    # Try ImageMagick first (if available)
    if check_imagemagick():
        return create_icon_imagemagick()
    
    # Fall back to Pillow
    try:
        return create_icon_pillow()
    except ImportError:
        print("❌ Neither ImageMagick nor Pillow found")
        return create_placeholder_icon()

def check_imagemagick():
    """Check if ImageMagick is available."""
    try:
        if sys.platform == "win32":
            # On Windows, try both 'magick' and 'convert'
            try:
                subprocess.check_output(["magick", "-version"], stderr=subprocess.DEVNULL)
                return "magick"
            except (subprocess.CalledProcessError, FileNotFoundError):
                subprocess.check_output(["convert", "-version"], stderr=subprocess.DEVNULL)
                return "convert"
        else:
            # On Unix-like systems
            subprocess.check_output(["convert", "-version"], stderr=subprocess.DEVNULL)
            return "convert"
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None

def create_icon_imagemagick():
    """Create icon using ImageMagick."""
    magick_cmd = check_imagemagick()
    if not magick_cmd:
        return False
    
    icon_png = "app_icon_256.png"
    ico_file = "app_icon.ico"
    
    # Create base icon (smaller than Mac version for Windows)
    if magick_cmd == "magick":
        # Windows ImageMagick syntax
        cmd = [
            "magick", "-size", "256x256",
            "gradient:#4A90E2-#357ABD",  # Blue gradient
            "-gravity", "center",
            "-pointsize", "36",
            "-fill", "white",
            "-font", "Arial-Bold",
            "-annotate", "+0-12", "FS",  # FluoroSpot initials
            "-pointsize", "16",
            "-annotate", "+0+12", "Analysis",
            icon_png
        ]
    else:
        # Unix ImageMagick syntax
        cmd = [
            "convert", "-size", "256x256",
            "gradient:#4A90E2-#357ABD",
            "-gravity", "center",
            "-pointsize", "36",
            "-fill", "white",
            "-font", "Arial-Bold",
            "-annotate", "+0-12", "FS",
            "-pointsize", "16",
            "-annotate", "+0+12", "Analysis",
            icon_png
        ]
    
    try:
        subprocess.run(cmd, check=True)
        print(f"✅ Base icon created: {icon_png}")
        
        # Convert to ICO format with multiple sizes
        ico_cmd = [magick_cmd, icon_png, "-define", "icon:auto-resize=256,128,64,48,32,16", ico_file]
        subprocess.run(ico_cmd, check=True)
        
        # Clean up PNG
        os.remove(icon_png)
        
        print(f"✅ ICO icon created: {ico_file}")
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"❌ ImageMagick icon creation failed: {e}")
        print("   Falling back to Pillow...")
        return False

def create_icon_pillow():
    """Create icon using Pillow (PIL)."""
    print("🐍 Using Pillow to create icon...")
    
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        print("❌ Pillow not found. Installing...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "Pillow"])
        from PIL import Image, ImageDraw, ImageFont
    
    # Create a 256x256 image with gradient-like effect
    icon_size = 256
    image = Image.new('RGBA', (icon_size, icon_size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    
    # Create a simple gradient background
    for y in range(icon_size):
        # Blue gradient from #4A90E2 to #357ABD
        r = int(74 + (53 - 74) * y / icon_size)
        g = int(144 + (122 - 144) * y / icon_size)
        b = int(226 + (189 - 226) * y / icon_size)
        draw.rectangle([(0, y), (icon_size, y + 1)], fill=(r, g, b, 255))
    
    # Add text
    try:
        # Try to use a system font
        if sys.platform == "win32":
            font_large = ImageFont.truetype("arial.ttf", 36)
            font_small = ImageFont.truetype("arial.ttf", 16)
        elif sys.platform == "darwin":
            font_large = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 36)
            font_small = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 16)
        else:
            # Linux
            font_large = ImageFont.load_default()
            font_small = ImageFont.load_default()
    except (OSError, IOError):
        # Fall back to default font
        font_large = ImageFont.load_default()
        font_small = ImageFont.load_default()
    
    # Draw "FS" text
    fs_text = "FS"
    fs_bbox = draw.textbbox((0, 0), fs_text, font=font_large)
    fs_width = fs_bbox[2] - fs_bbox[0]
    fs_height = fs_bbox[3] - fs_bbox[1]
    fs_x = (icon_size - fs_width) // 2
    fs_y = (icon_size - fs_height) // 2 - 12
    draw.text((fs_x, fs_y), fs_text, fill=(255, 255, 255, 255), font=font_large)
    
    # Draw "Analysis" text
    analysis_text = "Analysis"
    analysis_bbox = draw.textbbox((0, 0), analysis_text, font=font_small)
    analysis_width = analysis_bbox[2] - analysis_bbox[0]
    analysis_x = (icon_size - analysis_width) // 2
    analysis_y = fs_y + fs_height + 4
    draw.text((analysis_x, analysis_y), analysis_text, fill=(255, 255, 255, 255), font=font_small)
    
    # Save as ICO with multiple sizes
    ico_file = "app_icon.ico"
    
    # Create different sizes for the ICO
    sizes = [(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)]
    images = []
    
    for size in sizes:
        resized = image.resize(size, Image.Resampling.LANCZOS)
        images.append(resized)
    
    # Save as ICO
    images[0].save(ico_file, format='ICO', sizes=[img.size for img in images])
    
    print(f"✅ ICO icon created with Pillow: {ico_file}")
    return True

def create_placeholder_icon():
    """Create a placeholder icon."""
    print("📝 Creating placeholder Windows icon...")
    
    try:
        from PIL import Image
    except ImportError:
        print("❌ Cannot create placeholder without Pillow")
        return False
    
    # Create a simple solid color icon
    icon_size = 256
    image = Image.new('RGBA', (icon_size, icon_size), (74, 144, 226, 255))  # Blue color
    
    ico_file = "app_icon.ico"
    sizes = [(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)]
    images = [image.resize(size, Image.Resampling.LANCZOS) for size in sizes]
    
    images[0].save(ico_file, format='ICO', sizes=[img.size for img in images])
    
    print(f"✅ Placeholder icon created: {ico_file}")
    return True

def main():
    """Main icon creation process."""
    print("🚀 Starting Windows icon creation...")
    
    # Create icon
    success = create_simple_icon()
    
    if success:
        ico_path = Path("app_icon.ico")
        if ico_path.exists():
            size_kb = ico_path.stat().st_size / 1024
            print(f"✅ Windows app icon created successfully! ({size_kb:.1f} KB)")
        else:
            print("✅ Windows app icon creation completed!")
    else:
        print("❌ Failed to create Windows app icon")
        print("   You may need to manually create build_resources/app_icon.ico")
        print("   Or install ImageMagick or Pillow: pip install Pillow")

if __name__ == "__main__":
    main()