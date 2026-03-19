"""
Progress tracker.

Provides a simple progress bar wrapper for long-running migration
operations.  Falls back to plain print statements when `tqdm` is
not installed.
"""

import logging
import sys

logger = logging.getLogger(__name__)

_HAS_TQDM = False
try:
    from tqdm import tqdm as _tqdm
    _HAS_TQDM = True
except ImportError:
    pass


class ProgressTracker:
    """Wraps tqdm (if available) or emits plain text progress."""

    def __init__(self, total, desc="Migrating", unit="obj", quiet=False):
        self.total = total
        self.desc = desc
        self.unit = unit
        self.quiet = quiet
        self.current = 0
        self._bar = None

        if _HAS_TQDM and not quiet and total > 0:
            self._bar = _tqdm(total=total, desc=desc, unit=unit, file=sys.stderr)

    def update(self, n=1, suffix=""):
        self.current += n
        if self._bar:
            self._bar.update(n)
            if suffix:
                self._bar.set_postfix_str(suffix)
        elif not self.quiet and self.total > 0:
            pct = self.current * 100 // self.total
            print(f"\r  {self.desc}: {self.current}/{self.total} ({pct}%) {suffix}",
                  end="", flush=True)

    def close(self):
        if self._bar:
            self._bar.close()
        elif not self.quiet and self.total > 0:
            print()  # newline after the progress line

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
