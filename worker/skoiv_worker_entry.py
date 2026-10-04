"""PyInstaller entrypoint for the frozen worker (skoiv-worker.exe on Windows).

Kept as a tiny top-level script so the package's relative imports work when
frozen. See skoiv-worker.spec for the bundle definition.
"""

import os
import sys

# PyInstaller windowed builds on Windows can expose None stdio handles when
# the parent did not redirect them. The desktop shell always redirects; make
# the stream objects exist regardless so the JSON loop never crashes.
if sys.stdout is None:
    sys.stdout = os.fdopen(1, "w", encoding="utf-8", newline="\n")
if sys.stdin is None:
    sys.stdin = os.fdopen(0, "r", encoding="utf-8", newline="\n")
if sys.stderr is None:
    try:
        sys.stderr = os.fdopen(2, "w", encoding="utf-8", newline="\n")
    except OSError:
        sys.stderr = open(os.devnull, "w", encoding="utf-8")

from skoiv_worker.__main__ import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
