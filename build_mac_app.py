#!/usr/bin/env python3
"""
Build script for creating a Mac app bundle for FluoroSpot Analysis Tool.
This script uses PyInstaller to create a standalone .app bundle.
"""

import subprocess
import sys
import os
import shutil
from pathlib import Path

def check_dependencies():
  """Check if required build dependencies are installed."""
  try:
    import PyInstaller
    print(f"✅ PyInstaller found: {PyInstaller.__version__}")
  except ImportError:
    print("❌ PyInstaller not found. Installing...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])
  
  # Ensure project dependencies are installed
  print("📦 Installing project dependencies...")
  subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])

def clean_build():
  """Clean previous build artifacts."""
  print("🧹 Cleaning previous build artifacts...")
  paths_to_clean = ["build", "dist", "*.spec"]
  for path in paths_to_clean:
    if os.path.exists(path):
      if os.path.isdir(path):
        shutil.rmtree(path)
      else:
        os.remove(path)
      print(f"  Removed: {path}")

def create_app_bundle(target_arch="arm64"):
  """Create the Mac app bundle using PyInstaller."""
  arch_name = "Apple-Silicon" if target_arch == "arm64" else "Intel"
  print(f"🔨 Building Mac app bundle for {arch_name} ({target_arch})...")
  
  app_name = f"FluoroSpot Analysis {arch_name}"
  
  # PyInstaller command
  cmd = [
    sys.executable, "-m", "PyInstaller",
    "--onedir",  # Create a directory instead of a single file for better performance
    "--windowed",  # No console window
    "--target-arch", target_arch,  # Specify target architecture
    "--name", app_name,
    "--icon=build_resources/app_icon.icns",  # We'll create this
    "--add-data=gui/resources:fluorospot/gui/resources",
    "--add-data=config.yaml:fluorospot",
    "--hidden-import=tkinter",
    "--hidden-import=tkinter.ttk",
    "--hidden-import=tkinter.filedialog",
    "--hidden-import=tkinter.messagebox",
    "--hidden-import=pandas",
    "--hidden-import=numpy",
    "--hidden-import=scipy",
    "--hidden-import=openpyxl",
    "--hidden-import=yaml",
    "--exclude-module=matplotlib",  # Exclude if not needed to reduce size
    "--exclude-module=PIL",
    "--osx-bundle-identifier=org.iedb.fluorospot",
    "launch_gui.py"
  ]
  
  try:
    result = subprocess.run(cmd, check=True, capture_output=True, text=True)
    print(f"✅ {arch_name} app bundle created successfully!")
    return True, app_name
  except subprocess.CalledProcessError as e:
    print(f"❌ {arch_name} build failed: {e}")
    print(f"stdout: {e.stdout}")
    print(f"stderr: {e.stderr}")
    return False, None

def create_dmg(app_name):
  """Create a DMG file for distribution."""
  print(f"💿 Creating DMG file for {app_name}...")
  
  dmg_name = f"{app_name.replace(' ', '_')}.dmg"
  
  # Check if create-dmg is available (install with: brew install create-dmg)
  try:
    subprocess.check_output(["which", "create-dmg"])
  except subprocess.CalledProcessError:
    print("⚠️  create-dmg not found. Install with: brew install create-dmg")
    print("   Creating basic DMG instead...")
    return create_basic_dmg(app_name, dmg_name)
  
  # Use create-dmg for a professional DMG
  cmd = [
    "create-dmg",
    "--volname", app_name,
    "--volicon", "build_resources/app_icon.icns",
    "--window-pos", "200", "120",
    "--window-size", "600", "400",
    "--icon-size", "100",
    "--icon", f"{app_name}.app", "175", "120",
    "--hide-extension", f"{app_name}.app",
    "--app-drop-link", "425", "120",
    dmg_name,
    f"dist/{app_name}.app"
  ]
  
  try:
    subprocess.run(cmd, check=True)
    print(f"✅ DMG created: {dmg_name}")
    return True, dmg_name
  except subprocess.CalledProcessError as e:
    print(f"❌ DMG creation failed: {e}")
    return create_basic_dmg(app_name, dmg_name)

def create_basic_dmg(app_name, dmg_name):
  """Create a basic DMG file using hdiutil."""
  print(f"📀 Creating basic DMG for {app_name}...")
  
  # Create temporary directory for DMG contents
  temp_dir = "temp_dmg"
  os.makedirs(temp_dir, exist_ok=True)
  
  try:
    # Copy app to temp directory
    shutil.copytree(f"dist/{app_name}.app", f"{temp_dir}/{app_name}.app")
    
    # Create alias to Applications folder
    subprocess.run([
      "ln", "-sf", "/Applications", f"{temp_dir}/Applications"
    ], check=True)
    
    # Create DMG
    subprocess.run([
      "hdiutil", "create", "-volname", app_name,
      "-srcfolder", temp_dir, "-ov", "-format", "UDZO",
      dmg_name
    ], check=True)
    
    # Clean up
    shutil.rmtree(temp_dir)
    
    print(f"✅ Basic DMG created: {dmg_name}")
    return True, dmg_name
    
  except subprocess.CalledProcessError as e:
    print(f"❌ Basic DMG creation failed: {e}")
    # Clean up on failure
    if os.path.exists(temp_dir):
      shutil.rmtree(temp_dir)
    return False, None

def create_zip_distribution(app_name):
  """Create a ZIP file as an alternative distribution method."""
  print(f"📦 Creating ZIP distribution for {app_name}...")
  
  zip_name = f"{app_name.replace(' ', '_')}_Mac.zip"
  
  try:
    # Create zip file
    subprocess.run([
      "zip", "-r", zip_name, f"dist/{app_name}.app"
    ], check=True)
    
    print(f"✅ ZIP distribution created: {zip_name}")
    return True, zip_name
    
  except subprocess.CalledProcessError as e:
    print(f"❌ ZIP creation failed: {e}")
    return False, None

def main():
  """Main build process."""
  print("🚀 Starting Mac app build process for both Intel and Apple Silicon...")
  
  # Check we're on macOS
  if sys.platform != "darwin":
    print("❌ This script must be run on macOS to create Mac app bundles.")
    sys.exit(1)
  
  # Check dependencies
  check_dependencies()
  
  # Clean previous builds
  clean_build()
  
  # Build for both architectures
  architectures = [
    ("x86_64", "Intel"),
    ("arm64", "Apple Silicon")
  ]
  
  built_apps = []
  distribution_files = []
  
  for arch, arch_display in architectures:
    print(f"\n{'='*60}")
    print(f"Building for {arch_display} ({arch})")
    print(f"{'='*60}")
    
    # Create app bundle for this architecture
    success, app_name = create_app_bundle(target_arch=arch)
    if not success:
      print(f"❌ {arch_display} build failed! Continuing with other architectures...")
      continue
    
    built_apps.append((app_name, arch_display))
    
    # Show app bundle info
    app_path = Path(f"dist/{app_name}.app")
    if app_path.exists():
      size_mb = sum(f.stat().st_size for f in app_path.rglob('*') if f.is_file()) / (1024 * 1024)
      print(f"✅ {arch_display} app bundle: {app_path} ({size_mb:.1f} MB)")
    
    # Create distribution files for this architecture
    dmg_success, dmg_name = create_dmg(app_name)
    zip_success, zip_name = create_zip_distribution(app_name)
    
    if dmg_success:
      distribution_files.append(f"📀 {dmg_name}")
    if zip_success:
      distribution_files.append(f"📦 {zip_name}")
  
  # Final summary
  print(f"\n{'='*60}")
  print("🎉 Build Summary")
  print(f"{'='*60}")
  
  if built_apps:
    print("Built applications:")
    for app_name, arch_display in built_apps:
      print(f"  ✅ {app_name} ({arch_display})")
    
    print("\nDistribution files:")
    for dist_file in distribution_files:
      print(f"  {dist_file}")
    
    print("\nNext steps:")
    print("  1. Test both apps on clean Mac systems (Intel and Apple Silicon)")
    print("  2. Upload distribution files to GitHub releases")
    print("  3. Update documentation with download instructions")
  else:
    print("❌ No builds succeeded!")
    sys.exit(1)

if __name__ == "__main__":
  main()