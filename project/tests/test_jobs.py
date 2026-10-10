from __future__ import annotations

import json
import os
import subprocess
import sys

import pymupdf
import pytest
from conftest import EXPECTED

from vellric import cli, pdf_tools, runtime
from vellric.fidelity import native_section, words


def job(source, out, *args):
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "vellric",
            *args[:1],
            str(source),
            "--out",
            str(out),
            *args[1:],
            "--status-json",
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )
    return result.returncode, json.loads(result.stdout)


@pytest.fixture
def simple(tmp_path):
    path = tmp_path / "native.pdf"
    with pymupdf.open() as document:
        document.new_page(width=300, height=400).insert_text((30, 50), "Exact native words.")
        document.save(path)
    return path


def manifest(out):
    value = json.loads((out / "manifest.json").read_text())
    runtime.validate_bundle(out, value)
    return value


def test_native_full_job_and_golden(rich_pdf, tmp_path):
    out = tmp_path / "bundle"
    code, status = job(rich_pdf, out, "convert", "--structure", "native", "--layout")
    assert code == 0, status
    m = manifest(out)
    assert m["page_count"] == 2 and m["outstanding_candidates"] == []
    assert (out / "pages/000001/structured.md").read_text() == EXPECTED
    assert (
        out / "structured.md"
    ).read_text() == f"# Report\n\n## Page 1\n\n{EXPECTED}\n\n## Page 2\n\nA plain second page.\n"
    with pymupdf.open(rich_pdf) as document:
        assert [(out / f"pages/{n:06d}/native.txt").read_text() for n in (1, 2)] == [
            p.get_text("text") for p in document
        ]
    layout = json.loads((out / "pages/000001/layout.json").read_text())
    assert layout["tables"][0]["rows"][0] == ["Year", "Hearings", "Witnesses"]
    assert any(link.get("uri") == "https://example.org/archive" for link in layout["links"])
    assert m["pages"][1]["formatting_eligible"]


def test_strict_word_gate_unchanged():
    assert native_section("Year Total\n2019 4", ["Year Total 2019 5", "Year Total 2019 4"]) == (
        "Year Total 2019 4",
        None,
    )
    assert words("run_check()", inline=True) == ["run_check()"]
    assert words("runcheck()", inline=True) != words("run_check()", inline=True)


@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
@pytest.mark.parametrize("intrinsic", [0, 90, 270])
@pytest.mark.parametrize("negative_origin", [False, True])
def test_clip_pixels_and_named_geometry(simple, tmp_path, rotation, intrinsic, negative_origin):
    with pymupdf.open(simple) as document:
        page = document[0]
        if negative_origin:
            page.set_mediabox(pymupdf.Rect(-10, -20, 300, 400))
        page.set_cropbox(pymupdf.Rect(10, 20, 290, 380))
        page.set_rotation(intrinsic)
        path = tmp_path / "rotated.pdf"
        document.save(path)
    out = tmp_path / "render"
    clip = (10, 15, 100, 120)
    code, status = job(
        path,
        out,
        "render",
        "--dpi",
        "72",
        "--rotation",
        str(rotation),
        "--clip",
        ",".join(map(str, clip)),
    )
    assert code == 0, status
    with pymupdf.open(path) as document:
        expected = document[0].get_pixmap(
            matrix=pymupdf.Matrix(1, 1).prerotate(rotation), clip=pymupdf.Rect(clip), alpha=False
        )
        actual = pymupdf.Pixmap(str(out / "pages/000001/render-0001.png"))
        assert (actual.width, actual.height, actual.samples) == (
            expected.width,
            expected.height,
            expected.samples,
        )
        geometry = manifest(out)["pages"][0]["geometry"]
        displayed = pymupdf.Point(10, 15)
        original = displayed * pymupdf.Matrix(geometry["displayed_to_pdf"])
        rotation_matrix = document[0].rotation_matrix
        document[0].set_rotation(0)
        assert original * document[0].transformation_matrix * rotation_matrix == displayed


@pytest.mark.parametrize(
    "kind,expected", [("bad", "malformed-pdf"), ("password", "password-protected"), ("owner", None)]
)
def test_input_classification(tmp_path, kind, expected):
    path = tmp_path / "input.pdf"
    out = tmp_path / "out"
    if kind == "bad":
        path.write_bytes(b"%PDF-1.7\ninvalid")
    else:
        with pymupdf.open() as document:
            document.new_page().insert_text((30, 50), "Evidence")
            document.save(
                path,
                encryption=pymupdf.PDF_ENCRYPT_AES_256,
                user_pw="secret" if kind == "password" else "",
                owner_pw="owner",
            )
    code, status = job(path, out, "inspect")
    if expected:
        assert status["code"] == expected and code != 0 and not out.exists()
        if kind == "password":
            assert status["details"]["inspection"] == {
                "openable": True,
                "is_encrypted": True,
                "needs_password": True,
                "page_count": 1,
                "has_text_layer": None,
            }
    else:
        assert code == 0, status


def test_password_opt_in(simple, tmp_path):
    path = tmp_path / "encrypted.pdf"
    with pymupdf.open(simple) as document:
        document.save(
            path, encryption=pymupdf.PDF_ENCRYPT_AES_256, user_pw="secret", owner_pw="owner"
        )
    password = tmp_path / "password"
    password.write_text("secret\n")
    out = tmp_path / "out"
    code, status = job(path, out, "inspect", "--password-file", str(password))
    assert code == 0, status
    assert "secret" not in (out / "manifest.json").read_text()


def test_snapshot_hash_and_no_overwrite(simple, tmp_path):
    out = tmp_path / "out"
    code, status = job(simple, out, "inspect", "--expected-sha256", "0" * 64)
    assert code == 4 and status["code"] == "source-hash-mismatch" and not out.exists()
    out.mkdir()
    (out / "user").write_text("keep")
    code, status = job(simple, out, "inspect")
    assert code == 5 and (out / "user").read_text() == "keep"


def test_exclusive_publication_race(tmp_path):
    staging = tmp_path / "staging"
    staging.mkdir()
    (staging / "new").write_text("new")
    target = tmp_path / "target"
    target.mkdir()
    (target / "user").write_text("keep")
    with pytest.raises(runtime.JobError):
        runtime.publish(staging, target)
    assert staging.exists() and (target / "user").read_text() == "keep"


def test_raster_admission_prevents_giant_allocation(simple, tmp_path):
    out = tmp_path / "out"
    code, status = job(simple, out, "render", "--max-raster-bytes", "1000")
    assert code == 5 and status["code"] == "resource-limit" and not out.exists()


def test_ocr_never_reports_missing_recognition(tmp_path):
    path = tmp_path / "blank.pdf"
    with pymupdf.open() as document:
        document.new_page()
        document.save(path)
    out = tmp_path / "out"
    code, status = job(path, out, "convert", "--ocr", "never")
    assert code == 0, status
    m = manifest(out)
    assert m["recognition_completeness"] == "unrecognized-candidates" and m[
        "outstanding_candidates"
    ] == [1]
    assert (out / "pages/000001/text.txt").read_text() == ""
    assert (
        "[No text recovered from this page; check the original.]"
        in (out / "document.md").read_text()
    )


def test_native_searchable_copy(simple, tmp_path):
    out = tmp_path / "out"
    code, status = job(simple, out, "convert", "--searchable-pdf")
    assert code == 0, status
    assert (out / "searchable.pdf").read_bytes() == simple.read_bytes()
    assert manifest(out)["derivative_kind"] == "native-copy"


def test_bundle_tampering_refused(simple, tmp_path):
    out = tmp_path / "out"
    assert job(simple, out, "inspect")[0] == 0
    m = manifest(out)
    (out / "pages/000001/native.txt").write_text("tampered")
    with pytest.raises(runtime.JobError):
        runtime.validate_bundle(out, m)


@pytest.mark.parametrize(
    "fault", ["crash", "timeout", "memory", "missing", "corrupt", "shape", "mismatched-exit"]
)
def test_supervisor_refuses_failed_worker(simple, tmp_path, monkeypatch, fault):
    original = cli.subprocess.Popen

    def fake(command, **kwargs):
        if command[0] == "/bin/ps":
            return original(command, **kwargs)
        config = command[-1]
        script = (
            "import json,sys,time,os;from pathlib import Path;"
            "c=json.loads(Path(sys.argv[1]).read_text());"
        )
        scripts = {
            "crash": "os.kill(os.getpid(),9)",
            "timeout": "time.sleep(10)",
            "memory": "x=bytearray(200*1024*1024);time.sleep(10)",
            "missing": "pass",
            "corrupt": 'Path(c["result"]).write_text("bad")',
            "shape": 'Path(c["result"]).write_text(json.dumps({"status": [], "exit_code": 0}))',
            "mismatched-exit": (
                'Path(c["result"]).write_text(json.dumps({"status": '
                '{"schema": "vellric.status/1.0", "status": "complete", "code": "complete", '
                '"stage": "validated", "page_count": 1}, "exit_code": 0}));'
                "raise SystemExit(7)"
            ),
        }
        return original([sys.executable, "-c", script + scripts[fault], config], **kwargs)

    monkeypatch.setattr(cli.subprocess, "Popen", fake)
    options = vars(
        cli.parser().parse_args(
            [
                "inspect",
                str(simple),
                "--out",
                str(tmp_path / "out"),
                "--timeout-seconds",
                "0.3" if fault == "timeout" else "5",
                "--memory-mib",
                "100",
            ]
        )
    )
    with pytest.raises(runtime.JobError) as error:
        cli.run_job(options)
    expected = (
        "deadline"
        if fault == "timeout"
        else "resource-limit"
        if fault == "memory"
        else "internal-error"
    )
    assert error.value.code == expected
    assert not (tmp_path / "out").exists()
    assert not list(tmp_path.glob(".out.vellric-*"))


def test_coverage_is_sum_not_union(tmp_path):
    path = tmp_path / "overlap.pdf"
    with pymupdf.open() as image:
        image.new_page(width=100, height=100).insert_text((5, 50), "Image")
        png = image[0].get_pixmap().tobytes("png")
    with pymupdf.open() as document:
        page = document.new_page(width=100, height=100)
        page.insert_text((5, 50), "stale")
        page.insert_image(page.rect, stream=png)
        page.insert_image(page.rect, stream=png)
        document.save(path)
    assert pdf_tools.page_image_coverage(path) == [2.0]
    assert pdf_tools.ocr_page_numbers(path) == [1]


def test_environment_excludes_credentials_and_injection(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "secret")
    monkeypatch.setenv("PYTHONPATH", "bad")
    env = runtime.environment(tmp_path)
    assert (
        "OPENAI_API_KEY" not in env and "PYTHONPATH" not in env and env["OMP_THREAD_LIMIT"] == "1"
    )


def test_full_document_inspection_does_not_hide_read_failure(simple, monkeypatch):
    original = pymupdf.Page.get_text

    def fail(page, *a, **kw):
        raise RuntimeError("synthetic engine failure")

    monkeypatch.setattr(pymupdf.Page, "get_text", fail)
    with pytest.raises(pdf_tools.PdfReadOperationalError) as error:
        pdf_tools.page_texts(simple)
    assert error.value.inspection.page_count == 1 and error.value.inspection.page_texts is None
    monkeypatch.setattr(pymupdf.Page, "get_text", original)
    assert pdf_tools.page_texts(simple).page_count == 1


def test_zero_page_is_blocked(tmp_path):
    source = tmp_path / "zero.pdf"
    source.write_bytes(
        b"%PDF-1.4\n1 0 obj\n<</Type/Catalog/Pages 2 0 R>>\nendobj\n"
        b"2 0 obj\n<</Type/Pages/Count 0/Kids[]>>\nendobj\n"
        b"trailer\n<</Root 1 0 R>>\n%%EOF"
    )
    out = tmp_path / "out"
    code, status = job(source, out, "inspect")
    assert code == 3 and status["code"] == "degenerate-input" and not out.exists()
    assert status["details"]["inspection"]["page_count"] == 0
    assert status["details"]["inspection"]["openable"] is True


def test_render_arbitrary_clip_strips(tmp_path):
    source = tmp_path / "tall.pdf"
    with pymupdf.open() as document:
        page = document.new_page(width=200, height=9000)
        for y in range(20, 8990, 30):
            page.insert_text((10, y), f"Line at {y}")
        document.save(source)
    out = tmp_path / "out"
    code, status = job(
        source,
        out,
        "render",
        "--dpi",
        "72",
        "--strips",
        "--strip-pixels",
        "1000",
        "--clip",
        "5,10,195,8990",
    )
    assert code == 0, status
    renders = manifest(out)["pages"][0]["renders"]
    assert len(renders) >= 9 and renders[0]["clip"][1] == 10 and renders[-1]["clip"][3] == 8990
    assert all(r["height"] <= 1002 for r in renders)
    assert all(a["clip"][3] == b["clip"][1] for a, b in zip(renders, renders[1:]))


def test_output_budget_refuses_without_publication(simple, tmp_path):
    out = tmp_path / "out"
    code, status = job(simple, out, "inspect", "--max-output-bytes", "1")
    assert code == 5 and status["code"] == "resource-limit" and not out.exists()


def test_stdin_snapshot_and_progress(simple, tmp_path):
    out = tmp_path / "out"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "vellric",
            "inspect",
            "-",
            "--out",
            str(out),
            "--status-json",
            "--progress",
            "json",
        ],
        input=simple.read_bytes(),
        capture_output=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout)["source_sha256"] == runtime.digest(simple)
    events = [json.loads(line) for line in result.stderr.splitlines()]
    assert events and all(e["schema"] == "vellric.progress/1.0" for e in events)


def test_symlink_and_non_pdf_refused(simple, tmp_path):
    linked = tmp_path / "link.pdf"
    image = tmp_path / "image.png"
    with pymupdf.open(simple) as document:
        document[0].get_pixmap().save(image)
    assert job(image, tmp_path / "image-out", "inspect")[1]["code"] == "not-pdf"
    try:
        linked.symlink_to(simple)
    except OSError:
        assert os.name == "nt"
        pytest.skip("This Windows account cannot make links")
    assert job(linked, tmp_path / "symlink-out", "inspect")[1]["code"] == "pdf-open-operational"


def test_native_exception_frames_are_cleared_under_lock():
    class Object:
        def __del__(self):
            observed.append(pdf_tools.PDF_LOCK._is_owned())

    observed = []

    @pdf_tools.pdf_locked
    def fail():
        value = Object()
        assert value
        raise RuntimeError("failure")

    with pytest.raises(RuntimeError):
        fail()
    assert observed == [True]


def test_cancellation_reaps_worker_grandchild(simple, tmp_path, monkeypatch):
    original = cli.subprocess.Popen
    marker = tmp_path / "child-pid"

    def fake(command, **kwargs):
        if command[0] != sys.executable:  # Only the worker is replaced, not the process listing.
            return original(command, **kwargs)
        script = (
            "import os,subprocess,sys,time;from pathlib import Path;"
            "p=subprocess.Popen([sys.executable,'-c','import time;time.sleep(20)']).pid "
            "if os.name=='nt' else os.fork();"
            f"Path({str(marker)!r}).write_text(str(p)) if p else None;time.sleep(20)"
        )
        return original([sys.executable, "-c", script], **kwargs)

    monkeypatch.setattr(cli.subprocess, "Popen", fake)
    options = vars(
        cli.parser().parse_args(
            ["inspect", str(simple), "--out", str(tmp_path / "out"), "--timeout-seconds", "0.4"]
        )
    )
    with pytest.raises(runtime.JobError) as error:
        cli.run_job(options)
    assert error.value.code == "deadline" and not (tmp_path / "out").exists()
    child = int(marker.read_text())
    if os.name == "nt":
        listed = subprocess.run(
            ["tasklist", "/FI", f"PID eq {child}", "/FO", "CSV", "/NH"],
            capture_output=True,
            text=True,
        )
        assert listed.returncode == 0 and f'"{child}"' not in listed.stdout
        return
    result = subprocess.run(
        ["/bin/ps", "-o", "stat=", "-p", str(child)], capture_output=True, text=True
    )
    assert result.returncode != 0 or result.stdout.strip().startswith("Z")


def test_internal_links_remain_json_geometry(simple, tmp_path):
    source = tmp_path / "internal-link.pdf"
    with pymupdf.open(simple) as document:
        document.new_page()
        document[0].insert_link(
            {
                "kind": pymupdf.LINK_GOTO,
                "from": pymupdf.Rect(30, 40, 160, 60),
                "page": 1,
                "to": pymupdf.Point(30, 50),
            }
        )
        document.save(source)
    out = tmp_path / "out"
    code, status = job(source, out, "inspect", "--layout")
    assert code == 0, status
    data = json.loads((out / "pages/000001/layout.json").read_text())
    assert data["links"][0]["to"] == [30.0, 50.0]
    assert data["links"][0]["page"] == 1
    assert (out / "pages/000001/native.txt").read_text() == "Exact native words.\n"


@pytest.mark.parametrize(
    "args",
    [
        ("--ocr", "never", "--ocr-pages", "1"),
        ("--rotate-threshold", "nan"),
        ("--rotate-threshold", "-1"),
        ("--preflight-timeout-seconds", "0"),
        ("--ocr-pages", "2"),
    ],
)
def test_integration_ocr_controls_refuse_invalid_settings(simple, tmp_path, args):
    out = tmp_path / "invalid-controls"
    code, status = job(simple, out, "convert", *args)
    assert code == 2 and status["code"] == "usage"
    assert not out.exists()


def test_preflight_threshold_changes_processing_identity(simple, tmp_path):
    identities = []
    for index, threshold in enumerate((2, 3)):
        out = tmp_path / f"threshold-{index}"
        code, status = job(simple, out, "convert", "--rotate-threshold", str(threshold))
        assert code == 0, status
        record = manifest(out)
        identities.append(record["provenance"]["processing_fingerprint"])
        assert record["settings"]["rotate_threshold"] == threshold
        assert (out / "pages/000001/text.txt").read_text() == "Exact native words.\n"
    assert identities[0] != identities[1]
