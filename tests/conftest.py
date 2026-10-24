"""Make ``tests`` importable and install offline stubs before src.web loads.

Only used when the suite is run under pytest; ``python -m unittest`` works too
because the test module installs the stubs itself.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for path in (str(ROOT), str(ROOT / "tests")):
    if path not in sys.path:
        sys.path.insert(0, path)

import _stubs  # noqa: E402

_stubs.install_stubs()
