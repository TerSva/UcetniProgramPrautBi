"""Entry point — spouští desktop aplikaci účetního programu."""

from __future__ import annotations

import sys

from ui.app import run


if __name__ == "__main__":
    sys.exit(run())
