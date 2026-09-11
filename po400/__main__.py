"""Pulsox PO-400 CLI Package Entrypoint.

Allows running the package directly:
    python -m po400 [command]
"""

import sys
from po400.cli import main

if __name__ == "__main__":
    sys.exit(main())
