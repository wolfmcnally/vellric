# Adapted in part from Drawbridge ocr.py and mirror.py from an MIT source snapshot.
# Original copyright and MIT grant: LICENSES/drawbridge-MIT.txt.
"""One private complete document job. Only this process imports the PDF engine."""

from __future__ import annotations

import csv
import hashlib
import json
import mimetypes
import shutil
import sys
import threading
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from dataclasses import asdict
from pathlib import Path

from . import __version__, native, pdf_tools
from .errors import ConverterUnavailable, OcrOperationalError
from .fidelity import native_section
from .orientation import MAX_RENDER_SIDE, recover_page
from .runtime import BEHAVIOR, SCHEMA, JobError, digest, run_tool, validate_bundle, write_json


def reader(title: str, texts: list[str]) -> str:
    parts = [f"# {title}"]
    for number, text in enumerate(texts, 1):
        parts += [
            "",
            f"## Page {number}",
            "",
            text.strip() or "[No text recovered from this page; check the original.]",
        ]
    return ("\n".join(parts).rstrip() + "\n").replace("\x00", "")


def page_range(raw: str | None, count: int) -> list[int]:
    if raw is None:
        return list(range(1, count + 1))
    selected = set()
    try:
        for part in raw.split(","):
            pair = part.split("-")
            if len(pair) == 1:
                start = end = int(pair[0])
            elif len(pair) == 2:
                start, end = map(int, pair)
            else:
                raise ValueError
            if not 1 <= start <= end <= count:
                raise ValueError
            selected.update(range(start, end + 1))
    except ValueError as exc:
        raise JobError("usage", "Invalid page range", stage="settings") from exc
    return sorted(selected)


@pdf_tools.pdf_locked
def geometry_and_layout(source: Path, number: int, want_layout: bool) -> dict:
    mu = pdf_tools._pymupdf()
    with pdf_tools._open(source) as document:
        page = document[number - 1]
        intrinsic = page.rotation
        rotation, derotation = page.rotation_matrix, page.derotation_matrix
        # The rotated property loses CropBox offsets in the qualified engine.
        # Read the PDF-to-page transform with rotation disabled, then restore it.
        page.set_rotation(0)
        transform = page.transformation_matrix
        page.set_rotation(intrinsic)
        data = {
            "media_box": list(page.mediabox),
            "crop_box": list(page.cropbox),
            "displayed_rect": list(page.rect),
            "intrinsic_rotation": page.rotation,
            "pdf_to_unrotated": list(transform),
            "unrotated_to_displayed": list(rotation),
            "displayed_to_pdf": list(derotation * ~transform),
            "coordinate_frame": "displayed-page",
            "units": "pt",
        }
        if want_layout:
            raw = page.get_text("rawdict")
            # Embedded image bytes are not part of the JSON geometry contract.
            blocks = []
            for block in raw.get("blocks", []):
                if block.get("type") != 0:
                    continue
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        for char in span.get("chars", []):
                            char["quad"] = [
                                [point.x, point.y]
                                for point in mu.recover_char_quad(line["dir"], span, char)
                            ]
                blocks.append(block)
            data["layout"] = {
                "schema": "vellric.layout/1.0",
                "coordinate_frame": "unrotated-cropped-page",
                "blocks": blocks,
                "links": [],
                "images": page.get_image_info(),
            }
            for link in page.get_links():
                clean = {
                    k: list(v) if isinstance(v, (mu.Rect, mu.Point)) else v for k, v in link.items()
                }
                data["layout"]["links"].append(clean)
        return data


@pdf_tools.pdf_locked
def render_one(source: Path, number: int, target: Path, options: dict, clip=None) -> dict:
    mu = pdf_tools._pymupdf()
    with pdf_tools._open(source) as document:
        page = document[number - 1]
        rect = page.rect if clip is None else mu.Rect(clip)
        if not rect.is_valid or rect.is_empty or not page.rect.contains(rect):
            raise JobError(
                "usage", "Clip must lie within the displayed page", stage="render", page=number
            )
        dpi = float(options.get("_effective_dpi", options["dpi"]))
        scale = dpi / 72
        channels = 1 if options["colorspace"] == "gray" else 3
        pdf_tools.admit_raster(
            rect.width, rect.height, scale, 4 if options.get("pixel_fingerprints") else channels
        )
        matrix = mu.Matrix(scale, scale).prerotate(options["rotation"])
        predicted = (rect * matrix).irect
        if max(predicted.width, predicted.height) > MAX_RENDER_SIDE:
            raise JobError(
                "resource-limit",
                "Render side exceeds 30000 pixels; request strips or max-side",
                stage="render",
                page=number,
            )
        pix = page.get_pixmap(
            matrix=matrix,
            clip=rect,
            colorspace=mu.csGRAY if channels == 1 else mu.csRGB,
            alpha=False,
        )
        if max(pix.width, pix.height) > MAX_RENDER_SIDE:
            raise JobError(
                "resource-limit",
                "Render side exceeds 30000 pixels; request strips or max-side",
                stage="render",
                page=number,
            )
        if options["format"] == "jpeg":
            target.write_bytes(pix.tobytes("jpeg", jpg_quality=options["jpeg_quality"]))
        else:
            pix.save(target)
        result = {
            "path": str(target),
            "clip_frame": "displayed-page",
            "clip": list(rect),
            "requested_dpi": options["dpi"],
            "effective_dpi": dpi,
            "rotation": options["rotation"],
            "colorspace": options["colorspace"],
            "width": pix.width,
            "height": pix.height,
            "pixel_origin": [pix.x, pix.y],
            "displayed_to_pixels": list(matrix),
        }
        if options.get("pixel_fingerprints"):
            from .media import pixel_fingerprint

            result["fingerprint"] = pixel_fingerprint(pix)
        return result


def preflight(
    source: Path, selected: list[int], count: int, options: dict, work: Path, out: Path
) -> None:
    executable = shutil.which("ocrmypdf")
    if executable is None:
        raise JobError("dependency-unavailable", "ocrmypdf unavailable", stage="preflight")
    command = [
        executable,
        "--rotate-pages",
        "--rotate-pages-threshold",
        str(options["rotate_threshold"]),
        "--jobs",
        str(options["jobs"]),
        "--force-ocr",
        "--invalidate-digital-signatures",
        "--pages",
        ",".join(map(str, selected)),
        "--sidecar",
        str(work / "sidecar.txt"),
        "-l",
        options["language"],
        str(source),
        str(out),
    ]
    run_tool(
        command,
        timeout=min(options["preflight_timeout_seconds"], options["timeout_seconds"]),
        temp=work,
        code="ocr-preflight-refused",
        stage="preflight",
        tessdata_dir=options.get("tessdata_dir"),
    )
    inspection = pdf_tools.page_texts(out)
    if inspection.page_count != count:
        raise JobError(
            "page-count-drift", "Preflight changed document page count", stage="preflight"
        )


def execute(config: dict) -> dict:
    started = time.monotonic()
    options = config["options"]
    if options["command"] == "image":
        from .media import image_job

        return image_job(config)
    source = Path(config["source"])
    root = Path(config["staging"])
    work = Path(config["work"])

    def progress(stage, done, total, page=None):
        with (work / "progress.jsonl").open("a", encoding="utf-8") as f:
            f.write(
                json.dumps(
                    {
                        "schema": "vellric.progress/1.0",
                        "stage": stage,
                        "done": done,
                        "total": total,
                        "page": page,
                    }
                )
                + "\n"
            )

    pdf_tools.PASSWORD = config.get("password", "")
    pdf_tools.MAX_RASTER_BYTES = options["max_raster_bytes"]
    try:
        progress("inspection", 0, 1)
        with pdf_tools._open(source) as admission:
            if not admission.is_pdf:
                raise JobError("not-pdf", "Input is not PDF", stage="inspection")
            if admission.page_count > options["max_pages"]:
                raise JobError(
                    "resource-limit", "Page count exceeds admission limit", stage="inspection"
                )
        inspection = pdf_tools.page_texts(source)
        progress("inspection", 1, 1)
        mu = pdf_tools._pymupdf()
        count = inspection.page_count
        texts = list(inspection.page_texts)
        coverage = pdf_tools.page_image_coverage(source)
        candidates = pdf_tools.ocr_page_numbers(
            source, raster_threshold=options["raster_threshold"], inspection=inspection
        )
        write_json(work / "inspection.json", inspection.as_dict())
        selected = []
        if options["command"] == "convert":
            selected = (
                page_range(options["ocr_pages"], count)
                if options["ocr_pages"] is not None
                else list(range(1, count + 1))
                if options["ocr"] == "always"
                else candidates
                if options["ocr"] == "auto"
                else []
            )
        derivative_kind = None
        engine_facts = {}
        if options["ocr"] != "never":
            from .cli import doctor

            engine_facts = doctor(
                language=options["language"],
                tessdata_dir=options.get("tessdata_dir"),
                include_osd=options["preflight"] == "on",
            )
        if selected:
            if engine_facts.get("missing_languages"):
                raise JobError(
                    "dependency-unavailable",
                    "Requested language data unavailable",
                    stage="recognition",
                    details={"missing_languages": engine_facts["missing_languages"]},
                )
            if not engine_facts["engines"]["tesseract"]["available"]:
                raise JobError(
                    "dependency-unavailable", "tesseract unavailable", stage="recognition"
                )
            if engine_facts["engines"]["tesseract"].get("version") != "tesseract 5.5.2":
                raise JobError(
                    "dependency-unavailable",
                    "Unqualified Tesseract version; required 5.5.2",
                    stage="recognition",
                )
            if options["preflight"] == "on" and not engine_facts["engines"]["ocrmypdf"].get(
                "available", True
            ):
                raise JobError("dependency-unavailable", "ocrmypdf unavailable", stage="preflight")
            if (
                options["preflight"] == "on"
                and engine_facts["engines"]["ocrmypdf"].get("version") != "17.7.0"
            ):
                raise JobError(
                    "dependency-unavailable",
                    "Unqualified OCRmyPDF version; required 17.7.0",
                    stage="preflight",
                )
        if options["command"] == "convert" and selected:
            progress("recognition", 0, len(selected))
            if options["preflight"] == "on":
                derivative = work / "searchable.pdf"
                preflight(source, selected, count, options, work, derivative)
                if options["searchable_pdf"]:
                    shutil.copyfile(derivative, root / "searchable.pdf")
                    derivative_kind = "ocr-preflight"

            cancel_event = threading.Event()

            def recover(number):
                try:
                    return recover_page(
                        source,
                        number,
                        dpi=options["dpi"],
                        language=options["language"],
                        timeout=options["page_timeout_seconds"],
                        diagnostics=root / "diagnostics" if options["diagnostics"] else None,
                        tessdata_dir=options.get("tessdata_dir"),
                        cancel_event=cancel_event,
                    )
                except JobError as exc:
                    raise JobError(
                        exc.code, str(exc), stage=exc.stage, page=number, details=exc.details
                    ) from exc
                except OcrOperationalError as exc:
                    raise JobError(
                        "ocr-operational",
                        "OCR unavailable or failed",
                        stage="recognition",
                        page=number,
                    ) from exc

            recovered = []
            numbers = iter(selected)
            with ThreadPoolExecutor(max_workers=options["jobs"]) as pool:
                pending = {pool.submit(recover, n) for n in list(selected)[: options["jobs"]]}
                for _ in range(len(pending)):
                    next(numbers)
                try:
                    while pending:
                        done, pending = wait(pending, return_when=FIRST_COMPLETED)
                        # Observe every completed result before scheduling more work.
                        batch = [future.result() for future in done]
                        for item in batch:
                            recovered.append(item)
                            progress("recognition", len(recovered), len(selected), item.page)
                            number = next(numbers, None)
                            if number is not None:
                                pending.add(pool.submit(recover, number))
                except BaseException:
                    cancel_event.set()
                    for future in pending:
                        future.cancel()
                    raise
            recovered.sort(key=lambda item: item.page)
            for page in recovered:
                texts[page.page - 1] = page.text
        else:
            recovered = []
        if options.get("searchable_pdf") and not selected:
            shutil.copyfile(source, root / "searchable.pdf")
            derivative_kind = "native-copy"
        native_numbers = [n for n in range(1, count + 1) if n not in selected]
        want_structure = options.get("structure") == "native"
        layouts = (
            pdf_tools.page_layouts(
                source, list(range(1, count + 1)) if options["layout"] else native_numbers
            )
            if want_structure or options["layout"]
            else {}
        )
        proposals = (
            native.candidates({n: layouts[n] for n in native_numbers}) if want_structure else {}
        )
        records, structured = [], []
        render_pages = (
            page_range(options.get("pages"), count) if options["command"] == "render" else []
        )
        for number in range(1, count + 1):
            folder = root / "pages" / f"{number:06d}"
            folder.mkdir(parents=True)
            native_text = inspection.page_texts[number - 1]
            (folder / "native.txt").write_bytes(native_text.encode("utf-8"))
            (folder / "text.txt").write_bytes(texts[number - 1].encode("utf-8"))
            geometry = geometry_and_layout(source, number, options["layout"])
            record = {
                "number": number,
                "geometry": {k: v for k, v in geometry.items() if k != "layout"},
                "native_text_present": bool(native_text.strip()),
                "raster_coverage": coverage[number - 1],
                "coverage_formula": (
                    "sum(unrotated-image-bbox & displayed-page-rect).area/displayed-page-area"
                ),
                "ocr_candidate": number in candidates,
                "ocr_reason": "empty-native-text"
                if not native_text.strip()
                else "raster-coverage"
                if number in candidates
                else None,
                "method": "ocr" if number in selected else "pymupdf-text",
                "empty_text": not texts[number - 1].strip(),
                "formatting_eligible": bool(native_text.strip()) and number in native_numbers,
                "structure_requested": want_structure,
                "warnings": list(layouts[number].warnings) if number in layouts else [],
                "files": {
                    "native": str((folder / "native.txt").relative_to(root)),
                    "text": str((folder / "text.txt").relative_to(root)),
                },
            }
            rec = next((r for r in recovered if r.page == number), None)
            if rec:
                width, _ = pdf_tools.page_size(source, number)
                record["ocr"] = {
                    **rec.as_dict(),
                    "effective_dpi": min(
                        float(options["dpi"]), MAX_RENDER_SIDE * 72 / max(width, 1.0)
                    ),
                }
            if want_structure:
                formatted, reason = (
                    native_section(texts[number - 1], proposals[number])
                    if number in proposals
                    else (texts[number - 1], None)
                )
                structured.append(formatted)
                (folder / "structured.md").write_text(formatted, encoding="utf-8")
                record["formatting"] = {
                    "outcome": "fallback"
                    if reason
                    else "approved"
                    if number in proposals
                    else "ineligible",
                    "reason": reason,
                }
                record["files"]["structured"] = str((folder / "structured.md").relative_to(root))
            if options["layout"]:
                layout = geometry["layout"]
                # Interpreted runs retain the proven half-point/name/flag inference.
                layout["interpreted"] = asdict(layouts[number]) if number in layouts else None
                layout["tables"] = []
                if number in layouts:
                    for i, table in enumerate(layouts[number].tables, 1):
                        tables = folder / "tables"
                        tables.mkdir(exist_ok=True)
                        with (tables / f"{i:04d}.csv").open("w", encoding="utf-8", newline="") as f:
                            csv.writer(f).writerows(table.rows)
                        layout["tables"].append(asdict(table))
                write_json(folder / "layout.json", layout)
                record["files"]["layout"] = str((folder / "layout.json").relative_to(root))
            if number in render_pages:
                rect = geometry["displayed_rect"]
                clip = options.get("clip") or rect
                width, height = clip[2] - clip[0], clip[3] - clip[1]
                dpi = (
                    min(options["dpi"], options["max_side"] * 72 / max(width, height))
                    if options.get("max_side")
                    else options["dpi"]
                )
                cuts = ()
                if options["strips"]:
                    dpi = min(dpi, MAX_RENDER_SIDE * 72 / max(width, 1.0))
                    allowance = options["strip_pixels"] * 72 / dpi
                    cuts = pdf_tools.band_cuts(source, number, allowance, clip=clip)
                edges = (clip[1], *cuts, clip[3])
                record["renders"] = []
                extension = "jpg" if options["format"] == "jpeg" else options["format"]
                for i, (top, bottom) in enumerate(zip(edges, edges[1:]), 1):
                    target = folder / f"render-{i:04d}.{extension}"
                    rendered = render_one(
                        source,
                        number,
                        target,
                        options | {"_effective_dpi": dpi},
                        (clip[0], top, clip[2], bottom),
                    )
                    rendered["path"] = str(target.relative_to(root))
                    rendered["order"] = i
                    record["renders"].append(rendered)
            records.append(record)
            progress("artifacts", number, count, number)
        title = options.get("title") or config["title"]
        (root / "document.txt").write_bytes("\f".join(texts).encode("utf-8"))
        (root / "document.md").write_text(reader(title, texts), encoding="utf-8")
        if want_structure:
            (root / "structured.md").write_text(reader(title, structured), encoding="utf-8")
        subset = None
        if options.get("subset_pdf"):
            with pdf_tools._open(source) as original, mu.open() as derivative:
                start = previous = render_pages[0]
                for number in [*render_pages[1:], None]:
                    if number is not None and number == previous + 1:
                        previous = number
                        continue
                    derivative.insert_pdf(original, from_page=start - 1, to_page=previous - 1)
                    start = previous = number
                derivative.save(root / "subset.pdf", no_new_id=True)
            subset = {"path": "subset.pdf", "pages": render_pages}
        outstanding = [n for n in candidates if n not in selected]
        files = []
        for path in sorted(root.rglob("*")):
            if path.is_file():
                files.append(
                    {
                        "path": str(path.relative_to(root)),
                        "size": path.stat().st_size,
                        "sha256": digest(path),
                        "media_type": mimetypes.guess_type(path)[0] or "application/octet-stream",
                    }
                )
        manifest = {
            "schema": SCHEMA,
            "status": "complete",
            "job": options["command"],
            "source": {"sha256": config["sha256"], "size": config["size"]},
            "tool": {"name": "vellric", "version": __version__},
            "engines": {
                "pymupdf": mu.VersionBind,
                "mupdf": mu.VersionFitz,
                "ocr": engine_facts.get("engines"),
                "language_data": engine_facts.get("language_data", []),
            },
            "behavior": BEHAVIOR,
            "settings": {
                k: v
                for k, v in options.items()
                if k
                not in {
                    "input",
                    "out",
                    "password_file",
                    "password_stdin",
                    "temp_dir",
                    "tessdata_dir",
                }
            },
            "page_count": count,
            "inspection": inspection.as_dict(),
            "pages": records,
            "recognition_completeness": "unrecognized-candidates"
            if outstanding
            else "complete"
            if selected
            else "not-requested",
            "outstanding_candidates": outstanding,
            "derivative_kind": derivative_kind,
            "warnings": ["Derivative signatures may be invalidated"]
            if derivative_kind == "ocr-preflight"
            else [],
            "provenance": {
                "processing_fingerprint": hashlib.sha256(
                    json.dumps(
                        {
                            "behavior": BEHAVIOR,
                            "engine": mu.VersionBind,
                            "ocr": engine_facts.get("engines", {}),
                            "language_data": engine_facts.get("language_data", []),
                            "settings": {
                                k: options[k]
                                for k in (
                                    "ocr",
                                    "preflight",
                                    "structure",
                                    "dpi",
                                    "language",
                                    "raster_threshold",
                                    "rotate_threshold",
                                )
                            },
                        },
                        sort_keys=True,
                    ).encode()
                ).hexdigest(),
                "elapsed_seconds": time.monotonic() - started,
                "resource_enforcement": (
                    "process-group RSS/disk/deadline watchdog; raster admission; not a sandbox"
                ),
            },
            "files": files,
            "pdf_subset": subset,
        }
        validate_bundle(root, manifest)
        write_json(root / "manifest.json", manifest)
        return manifest
    except ConverterUnavailable as exc:
        raise JobError(
            "dependency-unavailable", "Qualified PyMuPDF unavailable", stage="inspection"
        ) from exc
    except pdf_tools.EncryptedPdfError as exc:
        raise JobError(
            "password-protected",
            "PDF requires a valid password",
            stage="inspection",
            details={"inspection": exc.inspection.as_dict()},
        ) from exc
    except pdf_tools.DegeneratePdfError as exc:
        raise JobError(
            "degenerate-input",
            "PDF contains no pages",
            stage="inspection",
            details={"inspection": exc.inspection.as_dict()},
        ) from exc
    except pdf_tools.MalformedPdfError as exc:
        raise JobError("malformed-pdf", "Malformed PDF", stage="inspection") from exc
    except pdf_tools.PdfOpenOperationalError as exc:
        raise JobError("pdf-open-operational", "PDF open failed", stage="inspection") from exc
    except pdf_tools.PdfReadOperationalError as exc:
        raise JobError(
            "pdf-read-operational",
            "Complete PDF traversal failed",
            stage="inspection",
            details={"inspection": exc.inspection.as_dict()},
        ) from exc
    except OcrOperationalError as exc:
        raise JobError(
            "ocr-operational", "OCR failed or returned malformed output", stage="recognition"
        ) from exc


def main() -> int:
    config = json.loads(Path(sys.argv[1]).read_text())
    result = Path(config["result"])
    try:
        manifest = execute(config)
        status = {
            "schema": "vellric.status/1.0",
            "status": "complete",
            "code": "complete",
            "stage": "validated",
            "page_count": manifest["page_count"],
        }
        exit_code = 0
    except JobError as exc:
        status, exit_code = exc.status(), exc.exit_code
    except Exception:
        status, exit_code = (
            JobError("internal-error", "Worker failed; no artifacts published").status(),
            5,
        )
    write_json(result, {"status": status, "exit_code": exit_code})
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
