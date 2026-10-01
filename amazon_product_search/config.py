"""Library-wide configuration: version string and default worker count."""

import os

__version__ = "0.1.2"

MAX_WORKERS = (os.cpu_count() or 4) // 2

__all__ = ["MAX_WORKERS", "__version__"]
