"""Allow ``python -m databossx`` as an alias for the ``databossx`` script."""

import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())
