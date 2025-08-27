#!/usr/bin/env python3
"""
Build script for creating a Windows executable for FluoroSpot Analysis Tool.
This script uses PyInstaller to create a standalone .exe file.
"""

import subprocess
import sys
import os
import shutil
import zipfile
from pathlib import Path

def check_dependencies():
    """Check if required build dependencies are installed."""
    try:
        import PyInstaller
        print(f"PyInstaller found: {PyInstaller.__version__}")
    except ImportError:
        print("PyInstaller not found. Installing...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])
    
    # Ensure project dependencies are installed
    print("Installing project dependencies...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])

def clean_build():
    """Clean previous build artifacts."""
    print("Cleaning previous build artifacts...")
    paths_to_clean = ["build", "dist", "*.spec"]
    for path in paths_to_clean:
        if os.path.exists(path):
            if os.path.isdir(path):
                shutil.rmtree(path)
            else:
                os.remove(path)
            print(f"  Removed: {path}")

def create_executable(build_type="onefile"):
    """Create the Windows executable using PyInstaller."""
    print(f"Building Windows executable ({build_type})...")
    
    app_name = "FluoroSpot_Analysis_Tool"
    
    # Check system architecture
    import platform
    current_arch = platform.machine()
    print(f"  Current system architecture: {current_arch}")
    print(f"  Target platform: Windows")
    
    # PyInstaller command
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile" if build_type == "onefile" else "--onedir",
        "--windowed",  # No console window
        "--name", app_name,
        "--distpath", "dist/windows",
        "--workpath", "build/windows",
        "--specpath", "build",
    ]
    
    # Add icon if it exists
    icon_path = "build_resources/app_icon.ico"
    if os.path.exists(icon_path):
        cmd.extend(["--icon", icon_path])
    else:
        print("Windows icon not found, building without icon")
    
    # Add data files and hidden imports
    cmd.extend([
        "--add-data", "gui/resources;fluorospot/gui/resources",
        "--add-data", "config.yaml;fluorospot",
        "--hidden-import", "tkinter",
        "--hidden-import", "tkinter.ttk",
        "--hidden-import", "tkinter.filedialog",
        "--hidden-import", "tkinter.messagebox",
        "--hidden-import", "pandas",
        "--hidden-import", "numpy",
        "--hidden-import", "scipy",
        "--hidden-import", "openpyxl",
        "--hidden-import", "yaml",
        "--exclude-module", "matplotlib",  # Exclude if not needed to reduce size
        "--exclude-module", "PIL",
        "launch_gui.py"
    ])
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print(f"Windows executable created successfully!")
        return True, app_name
    except subprocess.CalledProcessError as e:
        print(f"Windows build failed: {e}")
        print(f"stdout: {e.stdout}")
        print(f"stderr: {e.stderr}")
        return False, None

def create_installer():
    """Create an NSIS installer (if available)."""
    print("Checking for NSIS installer capability...")
    
    # Check if NSIS is available (would need to be installed separately)
    try:
        subprocess.check_output(["makensis", "/VERSION"])
        print("NSIS found, but installer creation not implemented yet")
        print("   This could be added in a future enhancement")
        return True, "installer_placeholder"
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("NSIS not found. Skipping installer creation.")
        return False, None

def create_zip_distribution(app_name, build_type="onefile"):
    """Create a ZIP file for distribution."""
    print(f"Creating ZIP distribution for {app_name}...")
    
    zip_name = f"{app_name}_Windows.zip"
    
    try:
        with zipfile.ZipFile(zip_name, 'w', zipfile.ZIP_DEFLATED) as zipf:
            if build_type == "onefile":
                # Single executable
                exe_path = f"dist/windows/{app_name}.exe"
                if os.path.exists(exe_path):
                    zipf.write(exe_path, f"{app_name}.exe")
                else:
                    print(f"Executable not found: {exe_path}")
                    return False, None
            else:
                # Directory distribution
                dist_dir = f"dist/windows/{app_name}"
                if os.path.exists(dist_dir):
                    for root, dirs, files in os.walk(dist_dir):
                        for file in files:
                            file_path = os.path.join(root, file)
                            arcname = os.path.relpath(file_path, f"dist/windows")
                            zipf.write(file_path, arcname)
                else:
                    print(f"Distribution directory not found: {dist_dir}")
                    return False, None
            
            # Add README or instructions if they exist
            readme_files = ["README.md", "README.txt", "INSTRUCTIONS.txt"]
            for readme in readme_files:
                if os.path.exists(readme):
                    zipf.write(readme, readme)
                    break
        
        print(f"ZIP distribution created: {zip_name}")
        return True, zip_name
        
    except Exception as e:
        print(f"ZIP creation failed: {e}")
        return False, None

def main():
    """Main build process for Windows executable."""
    build_type = "onefile"  # Can be "onefile" or "onedir"
    
    if len(sys.argv) > 1:
        if sys.argv[1] in ["onefile", "onedir"]:
            build_type = sys.argv[1]
        else:
            print("Usage: python build_windows.py [onefile|onedir]")
            print("  onefile: Create single executable (default)")
            print("  onedir:  Create directory with executable and dependencies")
            sys.exit(1)
    
    print(f"Starting Windows build process ({build_type})...")
    
    # Check we're on Windows (or allow cross-compilation)
    if sys.platform == "darwin":
        print("Running on macOS - cross-compilation to Windows may not work")
        print("   Consider running this on a Windows machine or GitHub Actions")
    elif sys.platform.startswith("linux"):
        print("Running on Linux - cross-compilation to Windows may not work")
        print("   Consider running this on a Windows machine or GitHub Actions")
    
    # Check dependencies
    check_dependencies()
    
    # Clean previous builds
    clean_build()
    
    # Create dist/windows directory
    os.makedirs("dist/windows", exist_ok=True)
    
    # Build the executable
    success, app_name = create_executable(build_type)
    if not success:
        print("Windows build failed!")
        sys.exit(1)
    
    # Show executable info
    if build_type == "onefile":
        exe_path = Path(f"dist/windows/{app_name}.exe")
        if exe_path.exists():
            size_mb = exe_path.stat().st_size / (1024 * 1024)
            print(f"Windows executable: {exe_path} ({size_mb:.1f} MB)")
    else:
        dist_path = Path(f"dist/windows/{app_name}")
        if dist_path.exists():
            size_mb = sum(f.stat().st_size for f in dist_path.rglob('*') if f.is_file()) / (1024 * 1024)
            print(f"Windows distribution: {dist_path} ({size_mb:.1f} MB)")
    
    # Create distribution files
    zip_success, zip_name = create_zip_distribution(app_name, build_type)
    installer_success, installer_name = create_installer()
    
    # Summary
    print(f"\n{'='*60}")
    print("Windows Build Complete")
    print(f"{'='*60}")
    
    print(f"Executable: {app_name}")
    
    distribution_files = []
    if zip_success:
        distribution_files.append(f"{zip_name}")
    if installer_success and installer_name != "installer_placeholder":
        distribution_files.append(f"{installer_name}")
    
    if distribution_files:
        print("Distribution files:")
        for dist_file in distribution_files:
            print(f"  {dist_file}")
    else:
        print("No distribution files created!")
        sys.exit(1)
    
    print("\nNext steps:")
    print("  1. Test the executable on a clean Windows system")
    print("  2. Upload distribution files to GitHub releases")
    print("  3. Update documentation with Windows download instructions")

if __name__ == "__main__":
    main()