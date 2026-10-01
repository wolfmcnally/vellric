# Copyright (c) 2026 Wolf McNally
# Adapted from Drawbridge source snapshot (origin retained privately).
# Original code retains MIT grant; see LICENSES/drawbridge-MIT.txt.
"""PyMuPDF-backed inspection, page selection, and page rendering.

Every PyMuPDF call this package makes lives here, so the import is optional
everywhere else and the exception mapping is in one place.

MuPDF is not safe to drive from several threads at once, even on separate
documents (PyMuPDF says so; a client's parallel workers crashed inside
``fz_load_jpx``). Every public function here holds ``PDF_LOCK`` while it uses
PyMuPDF. A client that calls PyMuPDF itself holds the same lock around those
calls. It is reentrant, so a locked function may call another.
"""

from __future__ import annotations

import functools
import threading
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from .errors import ConverterUnavailable, DocumentError, InherentlyUnprocessableError
from .runtime import PYMUPDF_VERSION


@dataclass(frozen=True)
class PdfInspection:
    """What one complete traversal established about a PDF."""

    openable: bool
    is_encrypted: bool | None
    needs_password: bool | None
    page_count: int | None
    has_text_layer: bool | None
    page_texts: tuple[str, ...] | None

    def as_dict(self, *, include_page_texts: bool = False) -> dict:
        data = {
            "openable": self.openable,
            "is_encrypted": self.is_encrypted,
            "needs_password": self.needs_password,
            "page_count": self.page_count,
            "has_text_layer": self.has_text_layer,
        }
        if include_page_texts:
            data["page_texts"] = list(self.page_texts) if self.page_texts is not None else None
        return data


UNKNOWN_INSPECTION = PdfInspection(False, None, None, None, None, None)


class MalformedPdfError(DocumentError):
    """The input bytes are not a readable PDF document."""

    def __init__(self, message: str, inspection: PdfInspection | None = None) -> None:
        self.inspection = inspection or UNKNOWN_INSPECTION
        super().__init__(message)


class EncryptedPdfError(MalformedPdfError, InherentlyUnprocessableError):
    """The PDF requires a user password the pipeline does not possess."""

    blocked_reason = "password-protected"


class DegeneratePdfError(MalformedPdfError, InherentlyUnprocessableError):
    """The PDF opened but has no structurally usable page."""

    blocked_reason = "degenerate-input"


class PdfOpenOperationalError(DocumentError):
    """The PDF engine could not open the bytes for an operational reason."""

    def __init__(self, message: str) -> None:
        self.inspection = UNKNOWN_INSPECTION
        super().__init__(message)


class PdfReadOperationalError(DocumentError):
    """The PDF opened, but a complete page traversal could not finish."""

    def __init__(self, message: str, inspection: PdfInspection) -> None:
        self.inspection = inspection
        super().__init__(message)


#  The one lock around every PyMuPDF call in this process (see the module docstring). The slow
# parts of the
#: stages that render or read pages (a recognition process, a model call) run outside it.
PDF_LOCK = threading.RLock()


def pdf_locked(function):
    """Run ``function`` holding ``PDF_LOCK``. If it raises, the frames that finished are
    cleared before the lock is
    released, so native documents and pixmaps an exception's traceback would keep alive are
    freed under the lock,
    not later on whatever thread discards the exception. (A native object caught in a
    reference cycle can still be
    freed by the cycle collector on any thread.)"""
    import traceback

    @functools.wraps(function)
    def locked(*args, **kwargs):
        with PDF_LOCK:
            try:
                return function(*args, **kwargs)
            except BaseException as exc:
                seen = set()
                while (
                    exc is not None and id(exc) not in seen
                ):  # the exception and every one it chains
                    seen.add(id(exc))
                    traceback.clear_frames(exc.__traceback__)
                    exc = exc.__cause__ or exc.__context__
                raise

    return locked


def _pymupdf():
    try:
        import pymupdf
    except ImportError as exc:  # pragma: no cover - exercised only without the dependency
        raise ConverterUnavailable("PyMuPDF is not installed") from exc
    if pymupdf.VersionBind != PYMUPDF_VERSION:
        raise ConverterUnavailable("Unqualified PyMuPDF version")
    return pymupdf


PASSWORD = ""
MAX_RASTER_BYTES = 256 * 1024 * 1024


def _open(path):
    mu = _pymupdf()
    try:
        document = mu.open(path)
    except (mu.EmptyFileError, mu.FileDataError, ValueError) as exc:
        raise MalformedPdfError("PDF document is malformed or empty") from exc
    except OSError as exc:
        raise PdfOpenOperationalError("PDF document could not be opened") from exc
    if document.needs_pass and not document.authenticate(PASSWORD):
        partial = PdfInspection(
            True, bool(document.is_encrypted), True, int(document.page_count), None, None
        )
        document.close()
        raise EncryptedPdfError("PDF document is password-protected", partial)
    return document


def admit_raster(width, height, scale, channels=3):
    from .runtime import JobError

    if (int(width * scale) + 2) * (int(height * scale) + 2) * channels > MAX_RASTER_BYTES:
        raise JobError("resource-limit", "Raster byte admission limit exceeded", stage="render")


@pdf_locked
def page_texts(pdf_path: Path) -> PdfInspection:
    """Traverse every page once and return the native text of each.

    Complete-or-refuse: the result carries exactly ``page_count`` strings or an
    exception is raised. There is never a partial page list.
    """
    pymupdf = _pymupdf()
    try:
        document = _open(pdf_path)
    except (pymupdf.EmptyFileError, pymupdf.FileDataError, ValueError) as exc:
        raise MalformedPdfError("PDF document is malformed or empty") from exc
    except OSError as exc:
        raise PdfOpenOperationalError("PDF document could not be opened") from exc
    try:
        with document:
            # An encrypted PDF opens successfully; without this check the
            # failure surfaces later, on page access, as a bare ValueError.
            # A permissions-only PDF has an empty user password and reads
            # normally after authenticate("").
            is_encrypted = bool(document.is_encrypted)
            needs_password = bool(document.needs_pass)
            page_count = int(document.page_count)
            partial = PdfInspection(True, is_encrypted, needs_password, page_count, None, None)
            if needs_password and not document.authenticate(PASSWORD):
                raise EncryptedPdfError("PDF document is password-protected", partial)
            if page_count == 0:
                raise DegeneratePdfError("PDF document has no pages", partial)
            try:
                pages = tuple(page.get_text("text") for page in document)
            except (OSError, RuntimeError, ValueError) as exc:
                raise PdfReadOperationalError(
                    "PDF document could not be read completely", partial
                ) from exc
            if len(pages) != page_count:
                raise PdfReadOperationalError(
                    "PDF page traversal returned an incomplete result", partial
                )
            return PdfInspection(
                True,
                is_encrypted,
                needs_password,
                page_count,
                any(text.strip() for text in pages),
                pages,
            )
    except (MalformedPdfError, PdfReadOperationalError):
        raise
    except OSError as exc:
        raise PdfReadOperationalError(
            "PDF document could not be read completely",
            PdfInspection(True, None, None, None, None, None),
        ) from exc


@pdf_locked
def ocr_page_numbers(
    pdf_path: Path,
    *,
    raster_threshold: float = 0.5,
    inspection: PdfInspection | None = None,
) -> list[int]:
    """Select scanned or textless pages, each judged independently (1-based).

    A page is selected when its native text is empty, or when its raster images
    cover at least ``raster_threshold`` of the page area. The coverage rule is a
    proxy for "this is a scan", and it deliberately catches scans that carry an
    old OCR layer. Small logos do not force native text through OCR; a large
    decorative background can over-select, which costs CPU but never content.

    ``inspection`` supplies already-extracted page texts so the document is not
    re-extracted; the images still have to be read from the document.
    """
    if not 0 < raster_threshold <= 1:
        raise ValueError("raster_threshold must be in (0, 1]")
    pymupdf = _pymupdf()
    texts = inspection.page_texts if inspection is not None else None
    selected: list[int] = []
    with _open(pdf_path) as document:
        if document.needs_pass and not document.authenticate(PASSWORD):
            raise EncryptedPdfError("PDF document is password-protected")
        if texts is not None and len(texts) != document.page_count:
            raise ValueError("inspection page count does not match the document")
        for number, page in enumerate(document, 1):
            text = texts[number - 1] if texts is not None else page.get_text()
            area = page.rect.get_area()
            image_area = sum(
                (pymupdf.Rect(image["bbox"]) & page.rect).get_area()
                for image in page.get_image_info()
            )
            if not text.strip() or (area > 0 and image_area >= area * raster_threshold):
                selected.append(number)
    return selected


@pdf_locked
def render_page_png(
    pdf_path: Path,
    page_number: int,
    target: Path,
    *,
    dpi: float = 300,
    rotation: int = 0,
    clip: tuple[float, float, float, float] | None = None,
) -> Path:
    """Render one page (1-based) to a PNG at ``dpi``, rotated by ``rotation`` degrees.

    ``clip`` limits the rendering to a rectangle (x0, y0, x1, y1) in the page's unrotated points.
    Reads the original; never writes to it. Safe to call from several threads.
    """
    pymupdf = _pymupdf()
    scale = dpi / 72
    with _open(pdf_path) as document:
        page = _page(document, page_number)
        matrix = pymupdf.Matrix(scale, scale).prerotate(rotation)
        rect = page.rect if clip is None else (pymupdf.Rect(clip) & page.rect)
        admit_raster(rect.width, rect.height, scale)
        page.get_pixmap(
            matrix=matrix, alpha=False, clip=None if clip is None else pymupdf.Rect(clip)
        ).save(target)
    return target


def _page(document, page_number: int):
    if document.needs_pass and not document.authenticate(PASSWORD):
        raise EncryptedPdfError("PDF document is password-protected")
    if not 1 <= page_number <= document.page_count:
        raise ValueError("page number out of range")
    return document[page_number - 1]


@pdf_locked
def page_size(pdf_path: Path, page_number: int) -> tuple[float, float]:
    """One page's width and height in points, unrotated. An image file is a one-page document."""
    with _open(pdf_path) as document:
        rect = _page(document, page_number).rect
        return rect.width, rect.height


# The grey rendering that band_cuts searches stays under this many pixels, however tall the page.
_CUT_SEARCH_PIXELS = 40_000_000


@pdf_locked
def band_cuts(
    pdf_path: Path, page_number: int, band_height: float, *, clip=None
) -> tuple[float, ...]:
    """Where to cut a page into horizontal bands no taller than ``band_height`` points, top
    to bottom.

    Each cut lies in the last quarter of its band's allowance, on the row whose shades vary
    least, and
    among equally quiet rows the lowest: a blank row between lines of text, wherever the
    page has one,
    so a cut rarely passes through a line. Returns the cut heights in points; none for a
    page that fits.
    """
    if band_height <= 0:
        raise ValueError("band height must be positive")
    pymupdf = _pymupdf()
    with _open(pdf_path) as document:
        page = _page(document, page_number)
        rect = page.rect if clip is None else pymupdf.Rect(clip)
        if not rect.is_valid or rect.is_empty or not page.rect.contains(rect):
            raise ValueError("invalid displayed clip")
        width, height = rect.width, rect.height
        if height <= band_height:
            return ()
        scale = min(1.0, (_CUT_SEARCH_PIXELS / max(width * height, 1.0)) ** 0.5)
        admit_raster(width, height, scale, 1)
        grey = page.get_pixmap(
            matrix=pymupdf.Matrix(scale, scale), colorspace=pymupdf.csGRAY, alpha=False, clip=rect
        )
        samples, stride, rows, columns = grey.samples, grey.stride, grey.height, grey.width
        spread = []
        for row in range(rows):
            line = samples[row * stride : row * stride + columns]
            spread.append(max(line) - min(line) if line else 0)
    cuts: list[float] = []
    top = 0.0
    while height - top > band_height:
        last = min(rows - 1, int((top + band_height) * scale))
        first = max(int(top * scale) + 1, int((top + band_height * 0.75) * scale))
        if first > last:
            first = last
        row = min(range(first, last + 1), key=lambda candidate: (spread[candidate], -candidate))
        cut = row / scale
        if cut <= top:
            cut = top + band_height
        cuts.append(cut)
        top = cut
    return tuple(cut + rect.y0 for cut in cuts)


@pdf_locked
def page_image_coverage(pdf_path: Path) -> list[float]:
    """Fraction of each page covered by raster images; useful for diagnostics."""
    pymupdf = _pymupdf()
    coverage: list[float] = []
    with _open(pdf_path) as document:
        if document.needs_pass and not document.authenticate(PASSWORD):
            raise EncryptedPdfError("PDF document is password-protected")
        for page in document:
            area = page.rect.get_area()
            image_area = sum(
                (pymupdf.Rect(image["bbox"]) & page.rect).get_area()
                for image in page.get_image_info()
            )
            coverage.append(image_area / area if area > 0 else 0.0)
    return coverage


@dataclass(frozen=True)
class Run:
    """A stretch of one line with one look and at most one link target."""

    text: str
    size: float
    bold: bool = False
    italic: bool = False
    mono: bool = False
    link: str | None = None


@dataclass(frozen=True)
class Line:
    runs: tuple[Run, ...]
    bbox: tuple[float, float, float, float]

    @property
    def text(self) -> str:
        return "".join(run.text for run in self.runs)


@dataclass(frozen=True)
class Table:
    bbox: tuple[float, float, float, float]
    rows: tuple[tuple[str, ...], ...]
    cells: tuple[tuple[float, ...] | None, ...] = ()


@dataclass(frozen=True)
class PageLayout:
    """What the PDF itself says about one page's typography: blocks of lines, and detected
    tables."""

    blocks: tuple[tuple[Line, ...], ...]
    tables: tuple[Table, ...] = ()
    warnings: tuple[str, ...] = ()


def _inside(point: tuple[float, float], rect: Sequence[float]) -> bool:
    return rect[0] <= point[0] <= rect[2] and rect[1] <= point[1] <= rect[3]


def _line_runs(line: dict, links: Sequence[tuple[tuple[float, ...], str]]) -> tuple[Run, ...]:
    runs: list[Run] = []
    for span in line.get("spans", ()):
        flags, font = int(span.get("flags", 0)), str(span.get("font", "")).lower()
        look = dict(
            size=round(float(span.get("size", 0.0)) * 2) / 2,
            bold=bool(flags & 16) or "bold" in font,
            italic=bool(flags & 2) or "italic" in font or "oblique" in font,
            mono=bool(flags & 8),
        )
        for char in span.get("chars", ()):
            box = char["bbox"]
            centre = ((box[0] + box[2]) / 2, (box[1] + box[3]) / 2)
            target = next((uri for rect, uri in links if _inside(centre, rect)), None)
            if (
                runs
                and runs[-1].link == target
                and all(getattr(runs[-1], key) == value for key, value in look.items())
            ):
                runs[-1] = Run(runs[-1].text + char["c"], link=target, **look)
            else:
                runs.append(Run(char["c"], link=target, **look))
    return tuple(runs)


@pdf_locked
def page_layouts(pdf_path: Path, page_numbers: Sequence[int]) -> dict[int, PageLayout]:
    """Typography, links and tables of the named pages (1-based), in the order the text layer reads.

    Table detection is a best effort: a page where it fails simply has no tables.
    """
    pymupdf = _pymupdf()
    quiet = getattr(pymupdf, "no_recommend_layout", None)
    if quiet is not None:
        quiet()  # otherwise table detection prints an advertisement into whatever reads our stdout
    layouts: dict[int, PageLayout] = {}
    with _open(pdf_path) as document:
        if document.needs_pass and not document.authenticate(PASSWORD):
            raise EncryptedPdfError("PDF document is password-protected")
        for number in page_numbers:
            if not 1 <= number <= document.page_count:
                raise ValueError("page number out of range")
            page = document[number - 1]
            links = [
                (tuple(link["from"]), str(link["uri"]))
                for link in page.get_links()
                if link.get("kind") == pymupdf.LINK_URI and link.get("uri")
            ]
            blocks = []
            for block in page.get_text("rawdict").get("blocks", ()):
                if block.get("type") != 0:
                    continue
                lines = tuple(
                    Line(_line_runs(line, links), tuple(line["bbox"]))
                    for line in block.get("lines", ())
                )
                lines = tuple(line for line in lines if line.runs)
                if lines:
                    blocks.append(lines)
            tables: list[Table] = []
            warnings = ()
            try:
                for found in page.find_tables().tables:
                    rows = tuple(
                        tuple("" if cell is None else str(cell) for cell in row)
                        for row in found.extract()
                    )
                    tables.append(
                        Table(
                            tuple(found.bbox),
                            rows,
                            tuple(tuple(cell) if cell else None for cell in found.cells),
                        )
                    )
            except Exception:  # noqa: BLE001 - detection is heuristic and must never cost the page its text
                tables = []
                warnings = ("table-detection-failed",)
            layouts[number] = PageLayout(tuple(blocks), tuple(tables), warnings)
    return layouts
