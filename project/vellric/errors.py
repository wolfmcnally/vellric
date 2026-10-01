# Copyright (c) 2026 Wolf McNally
# Adapted from Drawbridge source snapshot (origin retained privately).
# Original code retains MIT grant; see LICENSES/drawbridge-MIT.txt.
"""Typed failure taxonomy.

Membership in an exception class is the declaration of blast radius. A caller
processing many documents treats every ``DocumentError`` as local to one
document; anything else is a defect in the caller's environment or code.

Two families matter for routing:

* ``InherentlyUnprocessableError`` marks an input property no retry can repair
  (a password we do not have, a document with no pages). Callers should record
  a terminal ``blocked`` outcome keyed by the input's content hash so the same
  bytes can be re-admitted later if the blocker is lifted.
* Everything else is operational or malformed input and should be recorded as
  ``failed``: a replacement file, a repaired environment, or a retry may succeed.
"""

from __future__ import annotations

from typing import ClassVar


class DocumentError(Exception):
    """Base class for every document-local failure this package raises."""


class InherentlyUnprocessableError(DocumentError):
    """The input has a property that retrying cannot repair."""

    blocked_reason: ClassVar[str]


class ConverterUnavailable(DocumentError):
    """PyMuPDF cannot be imported."""


class OcrOperationalError(DocumentError):
    """OCR cannot run because an external tool is unavailable or timed out."""
