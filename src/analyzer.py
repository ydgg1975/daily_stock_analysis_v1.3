"""Compatibility shim for the package-based analyzer implementation.

The analyzer implementation lives in ``src/analyzer/``. This file remains so
legacy path-based tooling and broad diff checks do not treat ``src/analyzer.py``
as a deleted Python module.
"""

from src.analyzer.core import *  # noqa: F401,F403
