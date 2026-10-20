"""Moved to core.chat.alerts (ADR-001 step 3). This old name stays an alias of the same module object."""

import sys

from core.chat import alerts as _module

sys.modules[__name__] = _module
