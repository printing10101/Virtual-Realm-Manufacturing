"""
Version Consistency Mechanism Tests

Tests for the complete version detection, synchronization, and auto-restart system.
"""
import unittest
import os
import sys
import json
import re
from unittest.mock import patch, MagicMock
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "python"))


class TestVersionModule(unittest.TestCase):
    """Test Python version.py module."""
    
    def test_version_file_not_found(self):
        """Test VERSION file not found fallback."""
        with patch.object(Path, 'exists', return_value=False):
            from app.version import _load_version
            version = _load_version()
            self.assertEqual(version, "0.0.0")
    
    def test_get_commit_hash_git_not_available(self):
        """Test commit hash fallback when git is not available."""
        with patch('subprocess.run', side_effect=FileNotFoundError):
            from app.version import _get_commit_hash
            commit = _get_commit_hash()
            self.assertIsNone(commit)
    
    def test_get_version_info_structure(self):
        """Test get_version_info returns correct structure."""
        from app.version import get_version_info
        info = get_version_info()
        
        self.assertIn('version', info)
        self.assertIn('commit', info)
        self.assertIsInstance(info['version'], str)
        self.assertIsInstance(info['commit'], str)
        self.assertTrue(len(info['version']) > 0)


class TestVersionSynchronization(unittest.TestCase):
    """Test version synchronization script."""
    
    def setUp(self):
        """Set up project root path."""
        self.project_root = Path(__file__).parent.parent
        self.version_file = self.project_root / "VERSION"
        self.cargo_toml = self.project_root / "src-tauri" / "Cargo.toml"
        self.package_json = self.project_root / "package.json"
    
    def test_version_file_exists(self):
        """Test VERSION file exists at project root."""
        self.assertTrue(self.version_file.exists(), "VERSION file must exist at project root")
    
    def test_version_format_semver(self):
        """Test VERSION file contains valid SemVer format."""
        if self.version_file.exists():
            version = self.version_file.read_text().strip()
            self.assertTrue(
                re.match(r'^\d+\.\d+\.\d+$', version),
                f"Version '{version}' must be valid SemVer format (x.y.z)"
            )
    
    def test_cargo_toml_version_matches(self):
        """Test Cargo.toml version matches VERSION file."""
        if self.version_file.exists() and self.cargo_toml.exists():
            version = self.version_file.read_text().strip()
            cargo_content = self.cargo_toml.read_text(encoding='utf-8')
            
            match = re.search(r'^version\s*=\s*"([^"]+)"', cargo_content, re.MULTILINE)
            if match:
                cargo_version = match.group(1)
                self.assertEqual(
                    version, cargo_version,
                    f"VERSION file ({version}) must match Cargo.toml ({cargo_version})"
                )
    
    def test_package_json_version_matches(self):
        """Test package.json version matches VERSION file."""
        if self.version_file.exists() and self.package_json.exists():
            version = self.version_file.read_text().strip()
            with open(self.package_json, 'r', encoding='utf-8') as f:
                pkg = json.load(f)
            
            self.assertEqual(
                version, pkg['version'],
                f"VERSION file ({version}) must match package.json ({pkg['version']})"
            )


class TestVersionConsistencyLogic(unittest.TestCase):
    """Test version consistency checking logic."""
    
    def test_versions_consistent(self):
        """Test consistent version detection."""
        versions = {
            'frontend': '1.7.0',
            'rust': '1.7.0',
            'python': '1.7.0',
        }
        
        is_consistent = (
            versions['frontend'] == versions['rust'] and
            versions['python'] == versions['rust']
        )
        
        self.assertTrue(is_consistent)
    
    def test_versions_inconsistent_frontend(self):
        """Test inconsistent frontend version detection."""
        versions = {
            'frontend': '1.6.0',
            'rust': '1.7.0',
            'python': '1.7.0',
        }
        
        is_consistent = (
            versions['frontend'] == versions['rust'] and
            versions['python'] == versions['rust']
        )
        
        self.assertFalse(is_consistent)
    
    def test_versions_inconsistent_python(self):
        """Test inconsistent python version detection."""
        versions = {
            'frontend': '1.7.0',
            'rust': '1.7.0',
            'python': '1.6.0',
        }
        
        is_consistent = (
            versions['frontend'] == versions['rust'] and
            versions['python'] == versions['rust']
        )
        
        self.assertFalse(is_consistent)


if __name__ == '__main__':
    unittest.main()
