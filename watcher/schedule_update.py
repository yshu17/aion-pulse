"""Moved to core.schedule.schedule_update (ADR-001 step 3). This old name stays an alias of the same module object."""

import sys

from core.schedule import schedule_update as _module

sys.modules[__name__] = _module
