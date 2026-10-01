# Copyright (c) 2026 Wolf McNally
# Adapted from Drawbridge source snapshot (origin retained privately).
# Original code retains MIT grant; see LICENSES/drawbridge-MIT.txt.
"""Recover a scanned page's orientation by reading all four right-angle rotations.

Orientation detectors score their own confidence, and a confident guess can
still be upside down. So every selected page is rendered at 0, 90, 180 and 270
degrees, each rendering is recognised independently, and the rendering whose
words carry the most recognised alphanumeric characters at usable confidence
wins. The score measures recognition quality, not factual correctness.

A page too long to recognise in one image (a full-length screenshot of a
web page, say) is read in horizontal bands cut between lines of text: the
rotations are compared on the first band and the rest are read at the
winner. A page too wide is rendered at a lower resolution instead.
"""

from __future__ import annotations

import csv
import io
import shutil
import tempfile
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from .errors import OcrOperationalError
from .pdf_tools import band_cuts, page_size, render_page_png

ANGLES: tuple[int, ...] = (0, 90, 180, 270)
# Tesseract refuses an image whose side exceeds 32767 pixels, and PyMuPDF refuses a pixmap over
# about two
# gigabytes. A rendering whose longer side would pass MAX_RENDER_SIDE is read in bands
# BAND_PIXELS tall.
MAX_RENDER_SIDE = 30_000
BAND_PIXELS = 8_000
_TSV_REQUIRED = {"level", "block_num", "par_num", "line_num", "conf", "text"}


@dataclass(frozen=True)
class RecoveredPage:
    page: int
    text: str
    rotation: int
    score: float
    bands: int = 1

    def as_dict(self) -> dict:
        record = {"page": self.page, "rotation": self.rotation, "score": round(self.score, 1)}
        record["bands"] = self.bands
        return record


def tsv_text_and_score(raw: str) -> tuple[str, float]:
    """Regroup Tesseract TSV words into lines and score recognised-character confidence.

    Score = sum over words of (alphanumeric characters) x max(0, confidence - 50).
    A short accidental word therefore cannot beat a page of readable text.
    """
    reader = csv.DictReader(io.StringIO(raw), delimiter="\t", quoting=csv.QUOTE_NONE)
    if not _TSV_REQUIRED.issubset(reader.fieldnames or []):
        raise ValueError("Tesseract returned malformed TSV")
    lines: dict[tuple[str, str, str], list[str]] = {}
    score = 0.0
    for row in reader:
        if row["level"] != "5" or not (row["text"] or "").strip():
            continue
        word = row["text"].strip()
        try:
            confidence = float(row["conf"])
        except (TypeError, ValueError) as exc:
            raise ValueError("Tesseract returned malformed TSV") from exc
        score += sum(character.isalnum() for character in word) * max(0.0, confidence - 50)
        key = (row["block_num"], row["par_num"], row["line_num"])
        lines.setdefault(key, []).append(word)
    return "\n".join(" ".join(words) for words in lines.values()), score


def tesseract_executable() -> str:
    executable = shutil.which("tesseract")
    if executable is None:
        raise OcrOperationalError("tesseract unavailable")
    return executable


def recover_page(
    pdf_path: Path,
    page_number: int,
    *,
    dpi: int = 300,
    angles: Sequence[int] = ANGLES,
    language: str | None = None,
    timeout: int = 300,
    diagnostics: Path | None = None,
    tessdata_dir: str | None = None,
    cancel_event=None,
) -> RecoveredPage:
    """Recognise one page at every angle in ``angles`` and keep the best.

    The original PDF bytes are read, never written. A best score of zero
    yields an empty text, which the mirror marks explicitly.
    """
    executable = tesseract_executable()
    width, height = page_size(pdf_path, page_number)
    resolution = min(float(dpi), MAX_RENDER_SIDE * 72 / max(width, 1.0))
    scale = resolution / 72
    cuts = (
        band_cuts(pdf_path, page_number, BAND_PIXELS / scale)
        if height * scale > MAX_RENDER_SIDE
        else ()
    )
    edges = (0.0, *cuts, height)
    clips = (
        [None] if not cuts else [(0.0, top, width, bottom) for top, bottom in zip(edges, edges[1:])]
    )
    with tempfile.TemporaryDirectory(prefix="vellric-page-") as temp:

        def recognise(angle: int, band: int) -> tuple[str, float]:
            from .runtime import JobError

            if cancel_event is not None and cancel_event.is_set():
                raise JobError(
                    "deadline", "Recognition cancelled", stage="recognition", page=page_number
                )
            # Uncompressed: tesseract reads the same pixels, and PNG compression under the render
            # lock was two thirds of a wave's recognition time.
            target = render_page_png(
                pdf_path,
                page_number,
                Path(temp) / f"band-{band}-rotation-{angle}.pnm",
                dpi=resolution,
                rotation=angle,
                clip=clips[band],
            )
            command = [executable, str(target), "stdout"]
            if language:
                command += ["-l", language]
            command += ["--psm", "3", "tsv"]
            from .runtime import run_tool

            try:
                raw = run_tool(
                    command,
                    timeout=timeout,
                    temp=Path(temp),
                    tessdata_dir=tessdata_dir,
                    cancel_event=cancel_event,
                )
                if diagnostics is not None:
                    diagnostics.mkdir(parents=True, exist_ok=True)
                    (
                        diagnostics / f"page-{page_number:06d}-band-{band:04d}-rotation-{angle}.tsv"
                    ).write_text(raw, encoding="utf-8")
                return tsv_text_and_score(raw)
            except JobError as exc:
                raise JobError(
                    exc.code, str(exc), stage="recognition", page=page_number, details=exc.details
                ) from exc
            except ValueError as exc:
                raise JobError(
                    "ocr-operational",
                    "Tesseract returned malformed TSV",
                    stage="recognition",
                    page=page_number,
                ) from exc
            finally:
                target.unlink(missing_ok=True)

        candidates = [(angle, *recognise(angle, 0)) for angle in angles]
        angle, text, score = max(candidates, key=lambda candidate: candidate[2])
        texts = [text]
        for band in range(1, len(clips)):
            band_text, band_score = recognise(angle, band)
            texts.append(band_text)
            score += band_score
    text = "\n".join(part for part in texts if part)
    return RecoveredPage(page_number, text if score > 0 else "", angle, score, len(clips))
