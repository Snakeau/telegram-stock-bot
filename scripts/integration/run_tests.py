#!/usr/bin/env python
"""Quick test runner for asset resolution tests."""

import sys
import subprocess

# Run pytest
result = subprocess.run(
    [sys.executable, "-m", "pytest", "tests/test_asset_resolution.py", "-v", "--tb=short"],
    cwd="/Users/sergey/Work/AI PROJECTS/CHATBOT",
)
sys.exit(result.returncode)
