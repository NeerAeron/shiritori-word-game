"""Start Shiritori. Run it with: python play.py (add --help to see the options)."""

import sys

if sys.version_info < (3, 10):  # noqa: UP036 (a friendly message for old Pythons)
    sys.exit("Shiritori needs Python 3.10 or newer.")

from shiritori.cli import main

sys.exit(main())
