"""Moved to core.items.specs (ADR-001 step 3). This old name stays an alias of the same module object."""

import sys

from core.items import specs as _module

sys.modules[__name__] = _module
