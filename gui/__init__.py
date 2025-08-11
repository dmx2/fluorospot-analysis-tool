"""
FluoroSpot Analysis GUI
A user-friendly interface for the FluoroSpot analysis tool.
"""

__version__ = "1.0.0"
__author__ = "IEDB Tools Team"

# Import main GUI components for easy access
try:
  from .main import FluoroSpotGUI
except ImportError:
  # Allow package to be imported even if GUI dependencies aren't available
  pass