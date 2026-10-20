"""Moved to core.notify.notify_settings (ADR-001 step 3). This old name stays an alias of the same module object."""

import sys

from core.notify import notify_settings as _module

sys.modules[__name__] = _module
