"""Run agent integration tests programmatically via pytest.main()."""
import sys
from pathlib import Path

# Ensure python/ is in the path
sys.path.insert(0, str(Path(__file__).parent.parent / "python"))

import pytest

if __name__ == "__main__":
    test_file = str(Path(__file__).parent / "test_agent_integration_pytest.py")
    args = [test_file, "-v", "-s", "--tb=long"]
    exit_code = pytest.main(args)
    sys.exit(exit_code)
