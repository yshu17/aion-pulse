"""Moved to core.notify.alert_bridge (ADR-001 step 3). This old name stays an alias of the same module object."""

import sys

from core.notify import alert_bridge as _module

sys.modules[__name__] = _module
