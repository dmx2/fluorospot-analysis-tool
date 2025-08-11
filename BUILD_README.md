# Building Mac App Distribution

This document explains how to create a standalone Mac application for the FluoroSpot Analysis Tool that can be easily distributed to lab members.

## Overview

The build system creates a complete Mac application bundle (.app) that includes:
- Python runtime
- All required dependencies (pandas, numpy, scipy, etc.)
- The FluoroSpot analysis code and GUI
- Professional installer (DMG) and simple archive (ZIP)

## Quick Start

### Automated Build (Recommended)

The easiest way is to use GitLab CI/CD:

1. **Create a new tag** (triggers automatic build):
   ```bash
   git tag v1.0.0
   git push origin v1.0.0
   ```

2. **Download from GitLab Releases**: 
   - Go to your GitLab project → Releases
   - Download the DMG or ZIP file
   - Share with lab members

### Manual Build (Local Development)

For testing or custom builds on your Mac:

1. **Prerequisites**:
   ```bash
   # Install Homebrew if not already installed
   /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
   
   # Install required tools
   brew install python@3.11 imagemagick create-dmg
   ```

2. **Build the app**:
   ```bash
   # Navigate to the fluorospot directory
   cd fluorospot
   
   # Install build dependencies
   pip3 install -r build_requirements.txt
   
   # Create app icon (optional - will use placeholder if tools missing)
   cd build_resources && python3 create_app_icon.py && cd ..
   
   # Build the complete app bundle
   python3 build_mac_app.py
   ```

3. **Results**:
   - App bundle: `dist/FluoroSpot Analysis.app`
   - DMG installer: `FluoroSpot_Analysis.dmg`
   - ZIP archive: `FluoroSpot_Analysis_Mac.zip`

## Distribution Options

### DMG File (Recommended)
- Professional installer with drag-and-drop interface
- Users drag app to Applications folder
- Best user experience

### ZIP File (Alternative)
- Simple archive file
- Users extract and run directly
- Good for users uncomfortable with DMG files

## System Requirements

**For Building:**
- macOS 10.15 (Catalina) or later
- Python 3.11 or later
- Xcode Command Line Tools
- 2GB free disk space during build

**For End Users:**
- macOS 10.14 (Mojave) or later
- No additional software needed
- ~200MB disk space for installed app

## File Structure

```
fluorospot/
├── build_resources/
│   ├── app_icon.icns          # Mac app icon
│   ├── Info.plist             # App metadata
│   └── create_app_icon.py     # Icon generation script
├── build_mac_app.py           # Main build script
├── pyinstaller.spec           # Advanced build configuration
├── build_requirements.txt     # Build dependencies
└── BUILD_README.md            # This file

.gitlab-ci.yml                 # Automated CI/CD pipeline (root level)
```

## Troubleshooting

### Build Issues

**"PyInstaller not found"**:
```bash
pip3 install pyinstaller
```

**"create-dmg not found"**:
```bash
brew install create-dmg
# Or the script will create a basic DMG instead
```

**"ImageMagick not found"**:
```bash
brew install imagemagick
# Or the script will use a placeholder icon
```

### App Issues

**"App can't be opened" on first launch**:
- Right-click the app → Open
- This bypasses macOS Gatekeeper for unsigned apps
- Only needed on first launch

**App crashes on launch**:
- Check that the build completed successfully
- Ensure all dependencies were included
- Try building with `--debug` flag for more info

### GitLab CI/CD Issues

**No macOS runners available**:
- Ensure your GitLab instance has macOS runners configured
- Or use the manual build process locally

**Build fails in CI**:
- Check the job logs for specific error messages
- Ensure all dependencies are properly specified
- May need to adjust the `.gitlab-ci.yml` for your GitLab setup

## Customization

### Changing App Icon
1. Replace `build_resources/app_icon.icns` with your custom icon
2. Or modify `build_resources/create_app_icon.py` to generate different icon

### App Metadata
Edit `build_resources/Info.plist` or `pyinstaller.spec` to change:
- App name and version
- Bundle identifier
- Copyright information
- Supported file types

### Build Options
Modify `build_mac_app.py` to:
- Include/exclude specific modules
- Change app bundle structure
- Add custom build steps

## Security Notes

- The generated app is unsigned (would require Apple Developer account)
- Users may need to bypass Gatekeeper on first launch
- Consider code signing for wider distribution
- Never include sensitive data in the app bundle

## Support

For build issues:
1. Check this README
2. Look at GitLab CI job logs
3. Test manual build process locally
4. Verify all prerequisites are installed