import os
import sys
from pathlib import Path


def app_path(*sub_paths):
    """Get absolute path to resource, works for dev and for PyInstaller"""
    # PyInstaller creates a temp folder and stores path in _MEIPASS.
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):  # Check if running as a compiled app
        base_path = sys._MEIPASS
    else:
        base_path = os.path.abspath(".")
    return str(Path(base_path).joinpath(*sub_paths))
