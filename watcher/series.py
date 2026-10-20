"""Moved to core.chat.series (ADR-001 step 3). This old name stays an alias of the same module object."""

import sys

from core.chat import series as _module

sys.modules[__name__] = _module
