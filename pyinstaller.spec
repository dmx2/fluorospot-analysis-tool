# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for FluoroSpot Analysis Tool.
This file provides more control over the build process than command line options.
"""

from PyInstaller.utils.hooks import collect_data_files
import os

# Collect data files
gui_resources = collect_data_files('fluorospot.gui.resources')
config_files = [('config.yaml', 'fluorospot')]

# Add GUI resources data files
datas = gui_resources + config_files

# Hidden imports - modules that PyInstaller might miss
hiddenimports = [
  'tkinter',
  'tkinter.ttk',
  'tkinter.filedialog',
  'tkinter.messagebox',
  'pandas',
  'numpy',
  'scipy',
  'scipy.stats',
  'openpyxl',
  'yaml',
  'pathlib',
  'threading',
  'queue',
  'dataclasses'
]

# Excluded modules to reduce bundle size
excludes = [
  'matplotlib',
  'PIL',
  'IPython',
  'jupyter',
  'notebook',
  'pytest',
  'sphinx'
]

# Analysis configuration
a = Analysis(
  ['../launch_gui.py'],
  pathex=['..'],
  binaries=[],
  datas=datas,
  hiddenimports=hiddenimports,
  hookspath=[],
  hooksconfig={},
  runtime_hooks=[],
  excludes=excludes,
  noarchive=False
)

# Filter out unnecessary files
pyz = PYZ(a.pure, a.zipped_data, cipher=None)

# Create executable
exe = EXE(
  pyz,
  a.scripts,
  [],
  exclude_binaries=True,
  name='FluoroSpot Analysis',
  debug=False,
  bootloader_ignore_signals=False,
  strip=False,
  upx=True,
  console=False,  # No console window
  disable_windowed_traceback=False,
  argv_emulation=False,
  target_arch=None,
  codesign_identity=None,
  entitlements_file=None,
  icon='build_resources/app_icon.icns'
)

# Create application bundle
coll = COLLECT(
  exe,
  a.binaries,
  a.zipfiles,
  a.datas,
  strip=False,
  upx=True,
  upx_exclude=[],
  name='FluoroSpot Analysis'
)

# Mac app bundle
app = BUNDLE(
  coll,
  name='FluoroSpot Analysis.app',
  icon='build_resources/app_icon.icns',
  bundle_identifier='org.iedb.fluorospot',
  version='1.0.0',
  info_plist={
    'CFBundleDisplayName': 'FluoroSpot Analysis',
    'CFBundleName': 'FluoroSpot Analysis',
    'CFBundleShortVersionString': '1.0',
    'CFBundleVersion': '1.0.0',
    'NSHighResolutionCapable': True,
    'NSRequiresAquaSystemAppearance': False,
    'LSMinimumSystemVersion': '10.14',
    'NSHumanReadableCopyright': 'Copyright © 2024 IEDB Tools Team. All rights reserved.',
    'CFBundleGetInfoString': 'FluoroSpot Analysis Tool - Analyze Mabtech FluoroSpot immunoassay data',
    'CFBundleDocumentTypes': [
      {
        'CFBundleTypeExtensions': ['xlsx', 'xls'],
        'CFBundleTypeName': 'Excel Spreadsheet',
        'CFBundleTypeRole': 'Viewer',
        'LSHandlerRank': 'Alternate'
      },
      {
        'CFBundleTypeExtensions': ['yaml', 'yml'],
        'CFBundleTypeName': 'YAML Configuration',
        'CFBundleTypeRole': 'Editor',
        'LSHandlerRank': 'Alternate'
      }
    ]
  }
)