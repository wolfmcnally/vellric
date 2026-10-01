from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pymupdf
import pytest

from vellric import orientation, pdf_tools, runtime, worker

HEADER = (
    "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\t"
    "left\ttop\twidth\theight\tconf\ttext\n"
)


def row(conf, text, line=1):
    return f"5\t1\t1\t1\t{line}\t1\t0\t0\t10\t10\t{conf}\t{text}\n"


def test_tsv_scoring_grouping_and_malformed():
    text, score = orientation.tsv_text_and_score(
        HEADER + row(95, "Readable") + row(90, "evidence") + row(20, "noise", 2)
    )
    assert text == "Readable evidence\nnoise" and score == 680
    for raw in ("broken", HEADER + row("bad", "word")):
        with pytest.raises(ValueError):
            orientation.tsv_text_and_score(raw)


@pytest.mark.parametrize("shape", [(612, 792), (200, 9000), (9000, 100)])
def test_orientation_and_banding_proven_policy(tmp_path, monkeypatch, shape):
    source = tmp_path / "input.pdf"
    width, height = shape
    with pymupdf.open() as document:
        page = document.new_page(width=width, height=height)
        for y in range(20, int(height) - 10, 30):
            page.insert_text((10, y), f"Line at {y}", fontsize=11)
        document.save(source)
    seen = []

    def recognise(command, **kwargs):
        target = Path(command[1])
        band, angle = map(int, (target.stem.split("-")[1], target.stem.split("-")[-1]))
        pix = pymupdf.Pixmap(str(target))
        seen.append((band, angle, pix.width, pix.height))
        return HEADER + row(95 if angle == 0 else 10, f"Band{band}")

    monkeypatch.setattr(runtime, "run_tool", recognise)
    monkeypatch.setattr(orientation.shutil, "which", lambda name: "/synthetic/" + name)
    result = orientation.recover_page(source, 1)
    assert [angle for band, angle, *_ in seen if band == 0] == [0, 90, 180, 270]
    assert all(angle == 0 for band, angle, *_ in seen if band > 0)
    assert result.text == "\n".join(f"Band{n}" for n in range(result.bands))
    assert all(max(w, h) <= 30002 for _, _, w, h in seen)
    if height == 9000:
        assert result.bands >= 5 and all(max(w, h) <= 8002 for _, _, w, h in seen)
        # Retain the original Drawbridge quiet-cut oracle in the engine owner.
        cuts = pdf_tools.band_cuts(source, 1, 1905.0)
        assert len(cuts) >= 4 and cuts[0] < 1903
        edges = (0.0, *cuts, 9000.0)
        assert all(0 < bottom - top <= 1905.0 for top, bottom in zip(edges, edges[1:]))
        cores = [(y - 7, y + 1) for y in range(20, 8990, 30)]
        assert not [cut for cut in cuts for top, bottom in cores if top < cut < bottom]
        assert pdf_tools.band_cuts(source, 1, 9000.0) == ()
    if shape == (612, 792):
        assert seen[0][2:] == (2550, 3300)


def test_preflight_refusal_and_page_count_drift(tmp_path, monkeypatch):
    options = {
        "jobs": 1,
        "language": "eng",
        "timeout_seconds": 20,
        "rotate_threshold": 2.0,
        "preflight_timeout_seconds": 1800.0,
    }
    source = tmp_path / "source.pdf"
    output = tmp_path / "derivative.pdf"
    with pymupdf.open() as document:
        document.new_page()
        document.save(source)
    monkeypatch.setattr(worker.shutil, "which", lambda name: "/synthetic/" + name)

    def refuse(*a, **kw):
        raise runtime.JobError(
            "ocr-preflight-refused", "refused", details={"backend_returncode": 6}
        )

    monkeypatch.setattr(worker, "run_tool", refuse)
    with pytest.raises(runtime.JobError) as error:
        worker.preflight(source, [1], 1, options, tmp_path, output)
    assert (
        error.value.code == "ocr-preflight-refused"
        and error.value.details["backend_returncode"] == 6
    )
    monkeypatch.setattr(worker, "run_tool", lambda *a, **kw: shutil.copyfile(source, output))
    with pytest.raises(runtime.JobError) as error:
        worker.preflight(source, [1], 2, options, tmp_path, output)
    assert error.value.code == "page-count-drift"


def test_live_mixed_native_and_stale_scan(tmp_path):
    if not shutil.which("tesseract") or not shutil.which("ocrmypdf"):
        pytest.skip("Qualified system OCR engines required")
    source = tmp_path / "mixed.pdf"
    with pymupdf.open() as image:
        page = image.new_page(width=300, height=160)
        page.insert_text((20, 60), "Scanned source evidence", fontsize=16)
        png = page.get_pixmap(matrix=pymupdf.Matrix(3, 3)).tobytes("png")
    with pymupdf.open() as document:
        document.new_page(width=300, height=160).insert_text(
            (20, 60), "Exact native evidence.", fontsize=14
        )
        for stale in (False, True):
            page = document.new_page(width=300, height=160)
            page.insert_image(page.rect, stream=png)
            if stale:
                page.insert_text((20, 60), "stale wrong OCR", render_mode=3)
        document.save(source)
    before = runtime.digest(source)
    out = tmp_path / "out"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "vellric",
            "convert",
            str(source),
            "--out",
            str(out),
            "--ocr-pages",
            "2-3",
            "--rotate-threshold",
            "2.0",
            "--preflight-timeout-seconds",
            "60",
            "--jobs",
            "2",
            "--searchable-pdf",
            "--diagnostics",
            "--status-json",
        ],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    m = json.loads((out / "manifest.json").read_text())
    runtime.validate_bundle(out, m)
    assert m["outstanding_candidates"] == [] and m["recognition_completeness"] == "complete"
    assert (out / "pages/000001/text.txt").read_text() == "Exact native evidence.\n"
    for number in (2, 3):
        assert (out / f"pages/{number:06d}/text.txt").read_text() == "Scanned source evidence"
    assert "stale wrong OCR" in (out / "pages/000003/native.txt").read_text()
    assert list((out / "diagnostics").glob("*.tsv"))
    assert m["engines"]["language_data"]
    assert m["derivative_kind"] == "ocr-preflight" and runtime.digest(source) == before
    with pymupdf.open(out / "searchable.pdf") as document:
        assert document.page_count == 3


def test_live_processing_fingerprint_excludes_document_page_selection(tmp_path):
    if not shutil.which("tesseract") or not shutil.which("ocrmypdf"):
        pytest.skip("Qualified system OCR engines required")
    identities = []
    for index, page_number in enumerate((1, 2)):
        source = tmp_path / f"selection-{index}.pdf"
        with pymupdf.open() as document:
            for text in ("Native first page.", "Native second page."):
                document.new_page().insert_text((72, 72), text)
            document.save(source)
        out = tmp_path / f"selection-{index}"
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "vellric",
                "convert",
                str(source),
                "--out",
                str(out),
                "--ocr-pages",
                str(page_number),
                "--preflight",
                "off",
                "--status-json",
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert result.returncode == 0, result.stdout
        manifest = json.loads((out / "manifest.json").read_text())
        assert [p["number"] for p in manifest["pages"] if p["method"] == "ocr"] == [page_number]
        identities.append(manifest["provenance"]["processing_fingerprint"])
    assert identities[0] == identities[1]
