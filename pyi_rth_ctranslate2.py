"""Avoid loading CTranslate2's model-conversion toolchain in the desktop app."""

import sys
import types


sys.modules.setdefault(
    "ctranslate2.converters",
    types.ModuleType("ctranslate2.converters"),
)
