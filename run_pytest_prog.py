import os
import subprocess
import sys

os.chdir(r"c:\Users\Lenovo\Desktop\灵境制造（上线版）")

import pytest

result = pytest.main(['tests/test_agent_integration_pytest.py', '-v', '-s'])
print(f"\nExit code: {result}")
