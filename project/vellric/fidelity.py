# Copyright (c) 2026 Wolf McNally
# Adapted from Drawbridge source snapshot (origin retained privately).
# Original code retains MIT grant; see LICENSES/drawbridge-MIT.txt.
"""Exact Drawbridge native word gate; no model stages."""

import re
from collections.abc import Sequence

from .native import BULLETS

_SYNTAX = re.compile(r"^(#{1,6} |- |> )", re.M)
_HEADING = re.compile(r"^## (.+)\n", re.M)
_LINK_TARGET = re.compile(r"\]\([^()\s]*\)")
_INLINE = re.compile(
    rf"[*`|\\\[\]{BULLETS}]"
)  # a bullet glyph is often set tight against its first word
_RULE = re.compile(r"[-:]+")


def words(text: str, *, inline: bool = False) -> list[str]:
    """The word sequence the gate compares. ``inline`` also sets aside the inline Markdown
    the native
    pass writes (emphasis, code, link targets, table rules, bullet glyphs), on both sides alike."""
    text = _SYNTAX.sub("", text)
    if not inline:
        return text.split()
    text = _INLINE.sub("", _LINK_TARGET.sub("]", text))
    return [token for token in text.split() if not _RULE.fullmatch(token)]


def native_section(text: str, proposals: Sequence[str]) -> tuple[str, str | None]:
    """The first proposal whose words are the fidelity text's words, else the fidelity text."""
    for proposal in proposals:
        if words(proposal, inline=True) == words(text, inline=True):
            return proposal, None
    return text, "words-changed"
