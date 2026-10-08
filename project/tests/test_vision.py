from __future__ import annotations

import base64
import json
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pymupdf
import pytest

SECRET = "sk-test-0123456789-never-published"


def job(source, out, *args):
    result = subprocess.run(
        [sys.executable, "-m", "vellric", "convert", str(source), "--out", str(out)]
        + ["--preflight", "off", "--progress", "none", "--status-json", *args],
        capture_output=True,
        text=True,
        timeout=60,
    )
    return result.returncode, json.loads(result.stdout)


def manifest(out):
    return json.loads((out / "manifest.json").read_text())


def bundle_bytes(out):
    return b"".join(p.read_bytes() for p in sorted(out.rglob("*")) if p.is_file())


@pytest.fixture
def pdf(tmp_path):
    """Page 1 has native text, page 2 is a picture of text, page 3 has native text."""
    path = tmp_path / "mixed.pdf"
    with pymupdf.open() as document:
        first = document.new_page()
        first.insert_text((72, 100), "Alpha beta gamma delta.", fontsize=14)
        with pymupdf.open() as scratch:
            drawn = scratch.new_page()
            drawn.insert_text((72, 100), "Scanned words only.", fontsize=14)
            picture = drawn.get_pixmap(dpi=72)
        document.new_page().insert_image(pymupdf.Rect(0, 0, 612, 792), pixmap=picture)
        document.new_page().insert_text((72, 100), "Third page stays.", fontsize=14)
        document.save(path)
    return path


def adapter(tmp_path, name, replies):
    """A user-supplied vision program: image path in argv, prompt on stdin, Markdown out."""
    script = tmp_path / name
    script.write_text(
        f"#!{sys.executable}\n"
        "import json, os, sys\n"
        "assert open(sys.argv[1], 'rb').read(8) == b'\\x89PNG\\r\\n\\x1a\\n'\n"
        "assert 'Transcribe this scanned page' in sys.stdin.read()\n"
        f"replies = json.loads({json.dumps(json.dumps(replies))})\n"
        "sys.stdout.write(replies[os.environ['VELLRIC_VISION_PAGE']])\n"
    )
    script.chmod(0o755)
    return script


class Provider(BaseHTTPRequestHandler):
    """Stands in for both hosted APIs; the requested model name selects the outcome."""

    seen: list = []

    def log_message(self, *args):
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        headers = {name.lower(): value for name, value in self.headers.items()}
        Provider.seen.append((self.path, headers, body))
        outcome = body["model"]
        if self.path == "/v1/messages":
            stop = {"ok": "end_turn", "cut": "max_tokens", "refuse": "refusal"}[outcome]
            reply = {
                "id": "msg_test",
                "type": "message",
                "role": "assistant",
                "model": "served-model",
                "content": [] if stop == "refusal" else [{"type": "text", "text": "Claude read."}],
                "stop_reason": stop,
                "stop_sequence": None,
                "usage": {"input_tokens": 11, "output_tokens": 7},
            }
            if stop == "refusal":
                reply["stop_details"] = {"type": "refusal", "category": "cyber", "explanation": ""}
        else:
            finish = {"ok": "stop", "cut": "length", "refuse": "content_filter"}[outcome]
            reply = {
                "model": "served-model",
                "choices": [{"finish_reason": finish, "message": {"content": "Endpoint read."}}],
                "usage": {"prompt_tokens": 5, "completion_tokens": 3},
            }
        data = json.dumps(reply).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


@pytest.fixture
def provider():
    Provider.seen = []
    server = ThreadingHTTPServer(("127.0.0.1", 0), Provider)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()


def test_model_view_is_separate_and_cross_checked(tmp_path, pdf, monkeypatch):
    monkeypatch.setenv("UNRELATED_SECRET", SECRET)
    replies = {"1": "# Heading\n\nAlpha beta gamna delta with $x^2$.\n"}
    out = tmp_path / "out"
    code, status = job(
        pdf,
        out,
        "--ocr",
        "never",
        "--vision-provider",
        "command",
        "--vision-command",
        str(adapter(tmp_path, "reader", replies)),
        "--vision-pages",
        "1",
    )
    assert code == 0, status
    page = manifest(out)["pages"][0]
    # The exact native text stays the fidelity text; the model's reading is a second view.
    assert (out / "pages/000001/text.txt").read_bytes() == (
        out / "pages/000001/native.txt"
    ).read_bytes()
    assert page["method"] == "pymupdf-text"
    assert (out / page["files"]["vision"]).read_text() == replies["1"]
    assert page["vision"]["cross_check"] == {
        "reference": "native",
        "reference_words": 4,
        "vision_words": 6,
        "matched_words": 3,
        "agreement": 0.5,
        "reference_coverage": 0.75,
        "disagreements": 3,
        "disagreements_listed": 3,
    }
    spans = json.loads((out / page["files"]["vision_check"]).read_text())["spans"]
    assert {"reference": "gamma", "vision": "gamna"} in spans
    reader = (out / "document.md").read_text()
    assert "### Heading" in reader and "\n# Heading" not in reader and "gamna" in reader
    assert manifest(out)["vision"]["command"]["name"] == "reader"
    assert SECRET.encode() not in bundle_bytes(out)


def test_scan_read_only_by_the_model_takes_its_text(tmp_path, pdf):
    replies = {str(n): "Scanned words only.\n" for n in (1, 2, 3)}
    out = tmp_path / "out"
    code, status = job(
        pdf,
        out,
        "--vision-provider",
        "command",
        "--vision-command",
        str(adapter(tmp_path, "reader", replies)),
        "--vision-cross-check",
        "off",
    )
    assert code == 0, status
    record = manifest(out)
    # Automatic selection sends only the scanned page; no other reader ran on it.
    assert record["vision"]["pages"] == [2]
    assert [p["method"] for p in record["pages"]] == ["pymupdf-text", "vision", "pymupdf-text"]
    assert (out / "pages/000002/text.txt").read_text() == replies["2"]
    assert record["pages"][1]["vision"]["cross_check"] is None
    assert record["recognition_completeness"] == "complete"
    assert record["outstanding_candidates"] == []


@pytest.mark.parametrize("kind", ["openai", "anthropic"])
def test_hosted_provider_request_custody_and_typed_refusals(
    tmp_path, pdf, provider, monkeypatch, kind
):
    monkeypatch.setenv("VISION_TEST_KEY", SECRET)
    base = ["--ocr", "never", "--vision-provider", kind, "--vision-base-url", provider]
    base += ["--vision-api-key-env", "VISION_TEST_KEY", "--vision-pages", "2", "--vision-model"]
    out = tmp_path / "out"
    code, status = job(pdf, out, *base, "ok")
    assert code == 0, status
    path, headers, body = Provider.seen[-1]
    content = body["messages"][0]["content"]
    if kind == "openai":
        assert path == "/chat/completions" and headers["authorization"] == "Bearer " + SECRET
        image = content[1]["image_url"]["url"].split(",", 1)[1]
        expected = "Endpoint read.\n"
    else:
        assert path == "/v1/messages" and headers["x-api-key"] == SECRET
        image = content[0]["source"]["data"]
        expected = "Claude read.\n"
    assert base64.b64decode(image).startswith(b"\x89PNG") and body["model"] == "ok"
    if kind == "openai":
        monkeypatch.setenv("OPENAI_API_KEY", SECRET)
        unkeyed = ["--ocr", "never", "--vision-provider", kind, "--vision-base-url", provider]
        unkeyed += ["--vision-pages", "2", "--vision-model", "ok"]
        assert job(pdf, tmp_path / "unkeyed", *unkeyed)[0] == 0
        assert "authorization" not in Provider.seen[-1][1]
    record = manifest(out)
    assert (out / "pages/000002/vision.md").read_text() == expected
    assert record["pages"][1]["vision"]["served_model"] == "served-model"
    assert record["settings"]["vision_api_key_env"] == "VISION_TEST_KEY"
    assert SECRET.encode() not in bundle_bytes(out)
    for model, failure in (("cut", "vision-operational"), ("refuse", "vision-refused")):
        target = tmp_path / model
        code, status = job(pdf, target, *base, model)
        assert (code, status["code"], status.get("page")) == (5, failure, 2)
        assert not target.exists() and SECRET not in json.dumps(status)


def test_amend_redoes_only_the_named_pages(tmp_path, pdf):
    first = adapter(tmp_path, "first", {str(n): f"First reading {n}.\n" for n in (1, 2, 3)})
    second = adapter(tmp_path, "second", {"1": "Second reading 1.\n", "2": "Second reading 2.\n"})
    base, amended, again = tmp_path / "base", tmp_path / "amended", tmp_path / "again"
    common = ["--vision-provider", "command", "--vision-cross-check", "off"]
    assert job(pdf, base, *common, "--vision-command", str(first), "--vision-pages", "1-3")[0] == 0
    earlier, before = manifest(base), bundle_bytes(base)
    assert [p["method"] for p in earlier["pages"]] == ["pymupdf-text", "vision", "pymupdf-text"]
    args = [*common, "--vision-command", str(second), "--amend"]
    # Re-read page 1 only. Page 2 holds text that only the model read, so it must be carried.
    code, status = job(
        pdf, amended, *args, str(base), "--vision-pages", "1", "--raster-threshold", "1"
    )
    assert code == 0, status
    record = manifest(amended)
    for number in (2, 3):
        kept = earlier["pages"][number - 1]
        assert record["pages"][number - 1]["method"] == kept["method"]
        assert record["pages"][number - 1]["vision"] == kept["vision"]
        for name in kept["files"].values():
            assert (amended / name).read_bytes() == (base / name).read_bytes(), name
    assert (amended / "pages/000002/text.txt").read_text() == "First reading 2.\n"
    assert "vision_check" in earlier["pages"][2]["files"]
    assert (amended / "pages/000001/vision.md").read_text() == "Second reading 1.\n"
    assert (amended / "pages/000001/text.txt").read_bytes() == (
        amended / "pages/000001/native.txt"
    ).read_bytes()
    assert record["amended_from"]["amended_pages"] == [1]
    assert record["vision"]["command"]["name"] == "second" and record["vision"]["pages"] == [1]
    assert record["settings"]["raster_threshold"] == earlier["settings"]["raster_threshold"]
    fingerprint = record["provenance"]["processing_fingerprint"]
    assert fingerprint != earlier["provenance"]["processing_fingerprint"]
    assert bundle_bytes(base) == before
    # Re-reading the page whose text came from the model replaces that text.
    code, status = job(pdf, again, *args, str(amended), "--vision-pages", "2")
    assert code == 0, status
    assert (again / "pages/000002/text.txt").read_text() == "Second reading 2.\n"
    reader = (again / "document.md").read_text()
    assert "Second reading 1." in reader and "Second reading 2." in reader
    assert "First reading 3." in reader and "First reading 2." not in reader
    # An earlier result of different bytes is refused, and nothing is published.
    other = tmp_path / "other.pdf"
    with pymupdf.open() as document:
        for _ in range(3):
            document.new_page().insert_text((72, 100), "Different input.")
        document.save(other)
    refused = tmp_path / "refused"
    code, status = job(other, refused, *args, str(base), "--vision-pages", "2")
    assert (code, status["code"], status["stage"]) == (5, "artifact-invalid", "amend")
    assert not refused.exists()


REFUSED_SETTINGS = [
    (["--vision-model", "m"], "requires --vision-provider"),
    (["--amend", "."], "requires --vision-provider"),
    (["--vision-provider", "command"], "executable file"),
    (["--vision-provider", "openai", "--vision-base-url", "http://localhost:1"], "--vision-model"),
    (
        ["--vision-provider", "openai", "--vision-model", "m", "--vision-base-url", "file:///x"],
        "http(s)",
    ),
    (
        ["--vision-provider", "openai", "--vision-model", "m", "--vision-base-url", "http://u:p@h"],
        "http(s)",
    ),
    (
        ["--vision-provider", "openai", "--vision-model", "m", "--vision-base-url", "http://[bad"],
        "http(s)",
    ),
    (
        [
            "--vision-provider",
            "anthropic",
            "--vision-model",
            "m",
            "--vision-api-key-env",
            "UNSET_X",
        ],
        "UNSET_X",
    ),
    (
        ["--vision-provider", "anthropic", "--vision-model", "m", "--vision-base-url", "http://h"],
        "requires --vision-api-key-env",
    ),
    (
        [
            "--vision-provider",
            "openai",
            "--vision-model",
            "m",
            "--vision-base-url",
            "http://h",
            "--vision-cross-check",
            "off",
            "--searchable-pdf",
            "--preflight",
            "on",
        ],
        "Searchable PDF",
    ),
]


def test_vision_settings_refuse_before_any_work(tmp_path, pdf, monkeypatch):
    monkeypatch.delenv("UNSET_X", raising=False)
    for index, (arguments, reason) in enumerate(REFUSED_SETTINGS):
        out = tmp_path / f"out{index}"
        code, status = job(pdf, out, *arguments)
        assert (code, status["code"]) == (2, "usage") and not out.exists(), arguments
        assert reason in status["message"], (arguments, status["message"])
