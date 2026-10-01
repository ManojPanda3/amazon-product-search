"""Library-wide configuration: version string and default worker count."""

from __future__ import annotations

import os

__version__ = "0.1.2"

MAX_WORKERS = max(1, (os.cpu_count() or 4) // 2)  # Retained for backward compatibility: extraction is now serial, since parsing holds the GIL.

__all__ = ["MAX_WORKERS", "__version__"]
