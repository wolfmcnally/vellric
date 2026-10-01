"""Independent native pixel and derivative identities remain stable across the CLI boundary."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pymupdf
import pytest
from PIL import Image
from test_jobs import job, manifest

from vellric import media
from vellric.errors import ConverterUnavailable
from vellric.runtime import JobError


def fingerprint(pixels):
    shape = f"{pixels.width}:{pixels.height}:{pixels.n}:".encode()
    small = pymupdf.Pixmap(pymupdf.Pixmap(pymupdf.csGRAY, pixels), 9, 8)
    bits = 0
    for y in range(8):
        for x in range(8):
            bits = (bits << 1) | (small.samples[y * 9 + x] > small.samples[y * 9 + x + 1])
    return hashlib.sha256(shape + pixels.samples).hexdigest(), bits


def test_image_job_retains_exact_native_resize_and_fingerprint(tmp_path):
    source = tmp_path / "pixels.png"
    data = bytes(
        v
        for y in range(180)
        for x in range(240)
        for v in ((x * 3 + y) % 256, (y + 80) % 256, (x // 2 + y // 3) % 256)
    )
    pixels = pymupdf.Pixmap(pymupdf.csRGB, 240, 180, data, False)
    pixels.save(source)
    expected = pymupdf.Pixmap(pixels, 120, 90)
    before = hashlib.sha256(source.read_bytes()).hexdigest()
    code, status = job(source, tmp_path / "image", "image", "--width", "120", "--height", "90")
    assert code == 0, status
    m = manifest(tmp_path / "image")
    record = m["pages"][0]["fingerprint"]
    assert record["pixel_sha256"] == fingerprint(expected)[0]
    # Independently captured from the prior consumer engine on this fixed RGB pattern.
    assert record["difference_hash"] == 2748432088851663259
    with Image.open(tmp_path / "image/pages/000001/image.png") as actual:
        assert actual.size == (120, 90) and actual.tobytes() == expected.samples
    assert hashlib.sha256(source.read_bytes()).hexdigest() == before


def test_image_job_admits_raster_before_native_allocation(tmp_path, monkeypatch):
    source = tmp_path / "pixels.png"
    Image.new("RGB", (40, 30)).save(source)
    out = tmp_path / "blocked"
    code, status = job(source, out, "image", "--max-raster-bytes", "100")
    assert code == 5 and status["code"] == "resource-limit"
    assert not out.exists()
    code, status = job(source, tmp_path / "upsample", "image", "--width", "80", "--height", "60")
    assert code == 2 and status["code"] == "usage"
    assert not (tmp_path / "upsample").exists()

    # image_job owns this process-global limit in an isolated worker. Restore it in this
    # direct unit probe so later native-render proofs retain their own admission budget.
    monkeypatch.setattr(media.pdf_tools, "MAX_RASTER_BYTES", media.pdf_tools.MAX_RASTER_BYTES)
    config = {
        "source": str(source),
        "staging": str(tmp_path / "direct"),
        "options": {"max_raster_bytes": 100},
    }
    allocated = []

    def forbidden_native(*args):
        allocated.append(True)
        raise AssertionError("native allocation preceded admission")

    with monkeypatch.context() as patch:
        patch.setattr(media.pdf_tools, "_pymupdf", lambda: SimpleNamespace(Pixmap=forbidden_native))
        with pytest.raises(JobError) as caught:
            media.image_job(config)
        assert caught.value.code == "resource-limit" and not allocated
    config["options"]["max_raster_bytes"] = 1000000
    for error, expected_code in [
        (ConverterUnavailable("missing engine"), "dependency-unavailable"),
        (MemoryError("decode memory"), "resource-limit"),
    ]:

        def failed_engine():
            raise error

        with monkeypatch.context() as patch:
            patch.setattr(media.pdf_tools, "_pymupdf", failed_engine)
            with pytest.raises(JobError) as caught:
                media.image_job(config)
            assert caught.value.code == expected_code


def test_pdf_page_fingerprints_and_subset_retain_original_native_identities(tmp_path):
    source = tmp_path / "source.pdf"
    with pymupdf.open() as document:
        for number in range(3):
            page = document.new_page(width=200, height=300)
            page.insert_text((20, 50), f"Exact native page {number + 1}")
        document[1].add_ink_annot([[(20, 80), (40, 95), (65, 80)]])
        document.save(source)
    with pymupdf.open(source) as document:
        expected = [
            fingerprint(
                page.get_pixmap(
                    matrix=pymupdf.Matrix(2, 2), colorspace=pymupdf.csRGB, alpha=False, annots=True
                )
            )
            for page in document
        ]
        with pymupdf.open() as subset:
            subset.insert_pdf(document, from_page=1, to_page=2)
            subset.save(tmp_path / "expected.pdf", no_new_id=True)
    code, status = job(
        source, tmp_path / "raster", "render", "--dpi", "144", "--pixel-fingerprints"
    )
    assert code == 0, status
    actual = [p["renders"][0]["fingerprint"] for p in manifest(tmp_path / "raster")["pages"]]
    assert [(p["pixel_sha256"], p["difference_hash"]) for p in actual] == expected
    for suffix in ("one", "two"):
        code, status = job(
            source, tmp_path / suffix, "render", "--pages", "2-3", "--dpi", "72", "--subset-pdf"
        )
        assert code == 0, status
        assert (tmp_path / suffix / "subset.pdf").read_bytes() == (
            tmp_path / "expected.pdf"
        ).read_bytes()
        m = json.loads((tmp_path / suffix / "manifest.json").read_text())
        assert m["pdf_subset"] == {"path": "subset.pdf", "pages": [2, 3]}

    public_sample = Path(__file__).parents[1] / "docs/samples/inputs/native-report.pdf"
    code, status = job(
        public_sample, tmp_path / "public", "render", "--dpi", "144", "--pixel-fingerprints"
    )
    assert code == 0, status
    hashes = [
        p["renders"][0]["fingerprint"]["difference_hash"]
        for p in manifest(tmp_path / "public")["pages"]
    ]
    assert hashes == [9259559713303953408, 9223372036854775808]

    code, status = job(
        source,
        tmp_path / "lossy",
        "render",
        "--dpi",
        "144",
        "--pixel-fingerprints",
        "--format",
        "jpeg",
    )
    assert code == 2 and status["code"] == "usage"
    assert not (tmp_path / "lossy").exists()
