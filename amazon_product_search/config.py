"""Library-wide configuration: version string and default worker count."""

import os

__version__ = "0.1.2"

MAX_WORKERS = max(1, (os.cpu_count() or 4) // 2)  # CPU-bound parsing under a GIL-bound thread pool: more threads buy nothing.

__all__ = ["MAX_WORKERS", "__version__"]
