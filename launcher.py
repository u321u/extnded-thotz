"""PyInstaller entry script — equivalent to `python -m extnded_thotz`."""

import sys

from extnded_thotz.__main__ import main

if __name__ == "__main__":
    sys.exit(main())
