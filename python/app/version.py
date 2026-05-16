"""
Version Information Module

Loads version from root VERSION file and provides runtime version info.
Version is sourced from project root VERSION file (single source of truth).
"""

import subprocess
from pathlib import Path
from typing import Optional


def _get_project_root() -> Path:
    """Find project root by looking for VERSION file."""
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / "VERSION").exists():
            return parent
    return current.parent.parent


def _load_version() -> str:
    """Load version string from VERSION file."""
    version_file = _get_project_root() / "VERSION"
    if version_file.exists():
        return version_file.read_text().strip()
    return "0.0.0"


def _get_commit_hash() -> Optional[str]:
    """Get current git commit hash if available."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            cwd=_get_project_root(),
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass
    return None


VERSION = _load_version()
COMMIT = _get_commit_hash()


def get_version_info() -> dict:
    """Return version info as dictionary."""
    return {
        "version": VERSION,
        "commit": COMMIT or "unknown",
    }
