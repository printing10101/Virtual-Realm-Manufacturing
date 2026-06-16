"""Chatter module test configuration."""

import sys
from pathlib import Path

# Add python/ directory to sys.path BEFORE any app imports
_python_dir = Path(__file__).resolve().parent.parent.parent.parent.parent
if str(_python_dir) not in sys.path:
    sys.path.insert(0, str(_python_dir))
