from __future__ import annotations

import errno
import hashlib
import json
import os
import signal
import subprocess
import sys
import time

import pymupdf
import pytest

from vellric import cli, orientation, pdf_tools, runtime, worker


@pytest.fixture
def pdf(tmp_path):
    path = tmp_path / "native.pdf"
    with pymupdf.open() as doc:
        doc.new_page(width=100, height=200).insert_text((5, 20), "Native evidence")
        doc.save(path)
    return path


def config(source, base, *args):
    stage, work = base / "staging", base / "work"
    stage.mkdir()
    work.mkdir()
    options = vars(
        cli.parser().parse_args(
            ["convert", str(source), "--out", str(base / "out"), "--ocr", "never", *args]
        )
    )
    return dict(
        source=str(source),
        staging=str(stage),
        work=str(work),
        options=options,
        password="",
        sha256=runtime.digest(source),
        size=source.stat().st_size,
        title="Synthetic",
    )


def test_bundle_parent_alias_and_internal_symlink(pdf, tmp_path):
    out = tmp_path / "bundle"
    assert cli.main(["inspect", str(pdf), "--out", str(out), "--status-json"]) == 0
    m = json.loads((out / "manifest.json").read_text())
    alias = tmp_path / "alias"
    try:
        alias.symlink_to(tmp_path, target_is_directory=True)
    except OSError:  # Windows lets only some accounts make links.
        assert os.name == "nt"
        return
    runtime.validate_bundle(alias / "bundle", m)
    text = out / "pages/000001/text.txt"
    original = tmp_path / "same.txt"
    original.write_bytes(text.read_bytes())
    text.unlink()
    text.symlink_to(original)
    with pytest.raises(runtime.JobError, match="symlink") as error:
        runtime.validate_bundle(out, m)
    assert error.value.code == "artifact-invalid"


def test_render_side_precedes_allocation(tmp_path, monkeypatch):
    path = tmp_path / "long.pdf"
    with pymupdf.open() as doc:
        doc.new_page(width=200, height=9000)
        doc.save(path)

    def forbidden(*a, **kw):
        pytest.fail("Native allocation attempted")

    monkeypatch.setattr(pymupdf.Page, "get_pixmap", forbidden)
    options = vars(cli.parser().parse_args(["render", str(path), "--out", str(tmp_path / "out")]))
    with pytest.raises(runtime.JobError) as error:
        worker.render_one(path, 1, tmp_path / "image.png", options)
    assert error.value.code == "resource-limit" and error.value.page == 1


def test_ocr_failure_stops_pending_pages(tmp_path, monkeypatch):
    path = tmp_path / "many.pdf"
    with pymupdf.open() as doc:
        for _ in range(20):
            doc.new_page()
        doc.save(path)
    cfg = config(path, tmp_path, "--ocr", "always", "--preflight", "off", "--jobs", "1")
    monkeypatch.setattr(
        cli,
        "doctor",
        lambda **kw: {
            "engines": {
                "tesseract": {"available": True, "version": worker.QUALIFIED_TESSERACT},
                "ocrmypdf": {"available": False},
            },
            "language_data": [],
        },
    )
    calls = []

    def fail(source, number, **kw):
        calls.append(number)
        # Allow an eager scheduler to fill its queue before the first failure.
        time.sleep(0.02)
        raise runtime.JobError("ocr-operational", "Injected fault")

    monkeypatch.setattr(worker, "recover_page", fail)
    with pytest.raises(runtime.JobError) as error:
        worker.execute(cfg)
    assert calls == [1] and error.value.page == 1 and error.value.code == "ocr-operational"


def test_doctor_hashes_requested_actual_data(tmp_path, monkeypatch):
    data = tmp_path / "data"
    data.mkdir()
    for name in ["eng", "osd", "unused"]:
        (data / f"{name}.traineddata").write_bytes(name.encode())
    executable = tmp_path / "tesseract"
    executable.write_bytes(b"synthetic")
    monkeypatch.setattr(
        cli.shutil, "which", lambda name, **kw: str(executable) if name == "tesseract" else None
    )

    def probe(command, **kwargs):
        assert kwargs["env"]["TESSDATA_PREFIX"] == str(data)
        output = (
            "tesseract 5.5.2\n"
            if command[-1] == "--version"
            else f'List of available languages in "{data}" (3):\neng\nosd\nunused\n'
        )
        return subprocess.CompletedProcess(command, 0, stdout=output, stderr="")

    monkeypatch.setattr(cli.subprocess, "run", probe)
    info = cli.doctor(tessdata_dir=str(data))
    assert info["language_data"] == [
        {"name": f"{n}.traineddata", "sha256": hashlib.sha256(n.encode()).hexdigest()}
        for n in ["eng", "osd"]
    ]
    assert info["missing_languages"] == []


def test_doctor_timeout_is_unavailable(tmp_path, monkeypatch):
    executable = tmp_path / "tool"
    executable.write_bytes(b"synthetic")
    monkeypatch.setattr(cli.shutil, "which", lambda *a, **kw: str(executable))

    def timeout(*a, **kw):
        raise subprocess.TimeoutExpired(a[0], 15)

    monkeypatch.setattr(cli.subprocess, "run", timeout)
    info = cli.doctor()
    assert all(not info["engines"][name]["available"] for name in ["tesseract", "ocrmypdf", "gs"])


def test_recognition_fault_has_page(pdf, monkeypatch):
    monkeypatch.setattr(orientation, "tesseract_executable", lambda: "/synthetic/tesseract")

    def fail(*a, **kw):
        raise runtime.JobError("deadline", "Injected timeout")

    monkeypatch.setattr(runtime, "run_tool", fail)
    with pytest.raises(runtime.JobError) as error:
        orientation.recover_page(pdf, 1)
    assert error.value.page == 1 and error.value.stage == "recognition"


def test_table_failure_retains_fidelity(pdf, tmp_path, monkeypatch):
    def fail(*a, **kw):
        raise ValueError("Synthetic malformed table")

    monkeypatch.setattr(pymupdf.Page, "find_tables", fail)
    m = worker.execute(config(pdf, tmp_path, "--layout", "--structure", "native"))
    assert "table-detection-failed" in m["pages"][0]["warnings"]
    for file in ["native.txt", "text.txt"]:
        assert (tmp_path / "staging/pages/000001" / file).read_text() == "Native evidence\n"


@pytest.mark.parametrize("rect,coverage", [((0, 50, 10, 60), 0.005), ((80, 180, 130, 230), 0.02)])
def test_logo_and_clipped_coverage(tmp_path, rect, coverage):
    path = tmp_path / "logo.pdf"
    with pymupdf.open() as image:
        image.new_page(width=10, height=10)
        png = image[0].get_pixmap().tobytes("png")
    with pymupdf.open() as doc:
        page = doc.new_page(width=100, height=200)
        page.insert_text((5, 20), "Native evidence")
        page.insert_image(pymupdf.Rect(rect), stream=png, keep_proportion=False)
        doc.save(path)
    assert pdf_tools.page_image_coverage(path) == pytest.approx([coverage])
    assert pdf_tools.ocr_page_numbers(path) == []


def test_rotated_coverage_preserves_policy(tmp_path):
    path = tmp_path / "rotated.pdf"
    with pymupdf.open() as image:
        image.new_page(width=100, height=100)
        png = image[0].get_pixmap().tobytes("png")
    with pymupdf.open() as doc:
        page = doc.new_page(width=100, height=200)
        page.insert_text((5, 20), "Native evidence")
        page.insert_image(pymupdf.Rect(0, 100, 100, 200), stream=png)
        page.set_rotation(90)
        doc.save(path)
    assert pdf_tools.page_image_coverage(path) == [0] and pdf_tools.ocr_page_numbers(path) == []


def test_geometry_against_literal_pdf_ink(tmp_path):
    path = tmp_path / "ink.pdf"
    with pymupdf.open() as doc:
        page = doc.new_page(width=200, height=300)
        for key, value in [
            ("MediaBox", "[-10 -20 190 280]"),
            ("CropBox", "[0 20 180 260]"),
            ("Rotate", "90"),
        ]:
            doc.xref_set_key(page.xref, key, value)
        xref = doc.get_new_xref()
        doc.update_object(xref, "<<>>")
        doc.update_stream(xref, b"10 100 20 20 re f\n")
        doc.xref_set_key(page.xref, "Contents", f"{xref} 0 R")
        doc.save(path)
    out = tmp_path / "ink"
    assert (
        cli.main(
            [
                "render",
                str(path),
                "--out",
                str(out),
                "--dpi",
                "72",
                "--clip",
                "60,0,120,50",
                "--status-json",
            ]
        )
        == 0
    )
    pix = pymupdf.Pixmap(str(out / "pages/000001/render-0001.png"))
    assert sum(v < 128 for v in pix.samples) >= 1000
    m = json.loads((out / "manifest.json").read_text())
    point = pymupdf.Point(80, 10) * pymupdf.Matrix(m["pages"][0]["geometry"]["displayed_to_pdf"])
    assert (point.x, point.y) == pytest.approx((10, 100))
    blank = tmp_path / "blank"
    assert (
        cli.main(
            [
                "render",
                str(path),
                "--out",
                str(blank),
                "--dpi",
                "72",
                "--clip",
                "140,60,180,100",
                "--status-json",
            ]
        )
        == 0
    )
    assert min(pymupdf.Pixmap(str(blank / "pages/000001/render-0001.png")).samples) == 255


@pytest.mark.parametrize("format", ["pnm", "jpeg"])
def test_gray_render_formats(pdf, tmp_path, format):
    out = tmp_path / "image"
    assert (
        cli.main(
            [
                "render",
                str(pdf),
                "--out",
                str(out),
                "--format",
                format,
                "--colorspace",
                "gray",
                "--dpi",
                "72",
                "--status-json",
            ]
        )
        == 0
    )
    suffix = "jpg" if format == "jpeg" else format
    pix = pymupdf.Pixmap(str(out / f"pages/000001/render-0001.{suffix}"))
    assert pix.colorspace.n == 1 and (pix.width, pix.height) == (100, 200)


# Windows has one way for a parent to ask a child to stop: a break event sent to its group.
STOP_SIGNALS = [signal.CTRL_BREAK_EVENT] if os.name == "nt" else [signal.SIGINT, signal.SIGTERM]


@pytest.mark.parametrize("signum", STOP_SIGNALS)
def test_early_password_cancellation(pdf, tmp_path, signum):
    temp = tmp_path / "private"
    temp.mkdir()
    out = tmp_path / "out"
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "vellric",
            "inspect",
            str(pdf),
            "--out",
            str(out),
            "--password-stdin",
            "--temp-dir",
            str(temp),
            "--status-json",
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        **runtime.GROUP_FLAGS,
    )
    try:
        deadline = time.monotonic() + 5
        while not list(temp.glob("vellric-job-*")) and time.monotonic() < deadline:
            time.sleep(0.01)
        assert list(temp.glob("vellric-job-*"))
        process.send_signal(signum)
        stdout, stderr = process.communicate(timeout=5)
        assert process.returncode == 5, stderr
        assert (
            json.loads(stdout)["code"] == "deadline"
            and not out.exists()
            and not list(temp.iterdir())
        )
    finally:
        if process.poll() is None:
            process.kill()
        process.wait()


def test_password_input_and_temp_usage(pdf, tmp_path):
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "vellric",
            "inspect",
            str(pdf),
            "--out",
            str(tmp_path / "out"),
            "--password-stdin",
            "--status-json",
        ],
        input="unused\n",
        text=True,
        capture_output=True,
        timeout=10,
    )
    assert result.returncode == 0 and json.loads(result.stdout)["status"] == "complete"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "vellric",
            "inspect",
            str(pdf),
            "--out",
            str(tmp_path / "second"),
            "--temp-dir",
            str(tmp_path / "missing"),
            "--status-json",
        ],
        text=True,
        capture_output=True,
        timeout=10,
    )
    assert result.returncode == 2 and json.loads(result.stdout)["code"] == "usage"


def test_disk_failure_before_publish_cleans_staging(pdf, tmp_path, monkeypatch, capsys):
    def full(*a):
        raise OSError(errno.ENOSPC, "Injected full disk")

    monkeypatch.setattr(cli, "publish", full)
    out = tmp_path / "out"
    assert cli.main(["inspect", str(pdf), "--out", str(out), "--status-json"]) == 5
    assert json.loads(capsys.readouterr().out)["code"] == "internal-error"
    assert not out.exists() and not list(tmp_path.glob(".out.vellric-*"))


def test_native_eligibility_without_structure(pdf, tmp_path):
    m = worker.execute(config(pdf, tmp_path))
    assert m["pages"][0]["formatting_eligible"] and not m["pages"][0]["structure_requested"]


def test_unqualified_native_engine_refuses(pdf, tmp_path, monkeypatch):
    monkeypatch.setattr(pymupdf, "VersionBind", "unqualified")
    with pytest.raises(runtime.JobError) as error:
        worker.execute(config(pdf, tmp_path))
    assert error.value.code == "dependency-unavailable"
