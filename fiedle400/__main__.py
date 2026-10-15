"""Pulsox PO-400 CLI Package Entrypoint.

Allows running the package directly:
    python -m fiedle400 [command]
"""

import sys
from fiedle400.cli import main

if __name__ == "__main__":
    sys.exit(main())
