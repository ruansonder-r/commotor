"""Vercel entrypoint.

Vercel's Python runtime builds the whole app into a single function from this
file; `vercel.json` rewrites every path that is not a static file here.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from commoter.main import app  # noqa: E402

__all__ = ["app"]
