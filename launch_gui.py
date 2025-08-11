#!/usr/bin/env python3
"""
Launch script for FluoroSpot Analysis GUI.
This script properly sets up the Python path and imports to launch the GUI application.
"""

import sys
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent.resolve()
sys.path.insert(0, str(project_root))

# Now import and run the GUI
if __name__ == "__main__":
    from gui.main import main
    main()