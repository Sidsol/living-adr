"""Root conftest.

Ensures the repository root is importable so reusable test helpers under
``tests/conformance`` and ``tests/fakes`` (the feature-006 adapter conformance
surface that feature 007 reuses) can be imported as ``tests.conformance.*`` /
``tests.fakes.*`` regardless of the directory pytest is invoked from.
"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
