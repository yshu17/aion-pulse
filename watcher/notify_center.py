"""Moved to core.notify.notify_center (ADR-001 step 3). This old name stays an alias of the same module object."""

import sys

from core.notify import notify_center as _module

sys.modules[__name__] = _module
