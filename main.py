"""Dev-only entry point.

Adds ``src`` to ``sys.path`` so the package can be run directly.
Must be executed from the project root (``pyproject.toml`` directory).

Prefer ``uv run python -m gryps`` for production-like invocation.
"""

import sys

sys.path.insert(0, "src")

from gryps.__main__ import main

if __name__ == "__main__":
    main()
