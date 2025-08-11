"""
FluoroSpot Analysis Package

This package contains tools for analyzing FluoroSpot assay data, including
both command-line and graphical user interfaces.
"""

__version__ = "1.0.0"

# Import main analysis components for easy access
try:
  from .fluorospot_analysis import FluoroSpotAnalyzer, DataLoader, AnalysisConfig, AnalysisResult
except ImportError:
  # Allow package to be imported even if dependencies aren't available
  pass