"""Moved to core.bestiary.bestiary_labels (ADR-001 step 3). This old name stays an alias of the same module object."""

import sys

from core.bestiary import bestiary_labels as _module

sys.modules[__name__] = _module
