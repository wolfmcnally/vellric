"""Engine-independent identities for physical pages of exact PDF input bytes."""

from __future__ import annotations

import re

CONTRACT = "vellric.pdf-page-citations/1.0"


def page_anchor(source_sha256: str, number: int) -> str:
    """Identity is input bytes plus original one-based ordinal, never a printed label."""
    if not isinstance(source_sha256, str) or not re.fullmatch(r"[a-f0-9]{64}", source_sha256):
        raise ValueError("Invalid PDF source digest")
    if type(number) is not int or number < 1:
        raise ValueError("Invalid physical page ordinal")
    return f"vellric-pdf-{source_sha256}-page-{number:06d}"


def anchor_markup(anchor: str) -> str:
    """Only generated, validated identifiers may enter this HTML attribute."""
    if not isinstance(anchor, str) or not re.fullmatch(
        r"vellric-pdf-[a-f0-9]{64}-page-[0-9]{6,}", anchor
    ):
        raise ValueError("Invalid PDF page anchor")
    return f'<a id="{anchor}"></a>'


def validate_citations(manifest: dict) -> None:
    """Check the versioned mapping without importing a PDF engine or parsing Markdown."""
    pages = manifest["pages"]
    if manifest.get("job") == "image":
        if "page_citations" in manifest or any("anchor" in page for page in pages):
            raise ValueError("Images cannot declare PDF page citations")
        return
    if manifest.get("job") not in {"inspect", "convert", "render"}:
        raise ValueError("Unknown document job")
    if manifest.get("page_citations") != {"schema": CONTRACT}:
        raise ValueError("Missing or unsupported PDF page citation contract")
    source = manifest.get("source", {}).get("sha256")
    for page in pages:
        if page.get("anchor") != page_anchor(source, page["number"]):
            raise ValueError("PDF page anchor does not match source and physical ordinal")
