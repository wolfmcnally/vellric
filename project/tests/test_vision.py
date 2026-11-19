from __future__ import annotations

import base64
import json
import os
import select
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import Mock

import pymupdf
import pytest
from PIL import Image

from vellric import broker, cli, vision
from vellric.runtime import JobError

SECRET = "sk-test-0123456789-never-published"
# Windows starts the stand-in program through a command file of the same name.
SUFFIX = ".cmd" if os.name == "nt" else ""


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


def adapter(tmp_path, name, replies, key="VELLRIC_VISION_PAGE"):
    """A user-supplied vision program: image path in argv, prompt on stdin, Markdown out."""
    script = tmp_path / name
    script.write_text(
        f"#!{sys.executable}\n"
        "import json, os, sys, time\n"
        "assert 'VELLRIC_TEST_COMMAND_ENV_DENIED' not in os.environ\n"
        "assert open(sys.argv[1], 'rb').read(8) == b'\\x89PNG\\r\\n\\x1a\\n'\n"
        "told = sys.stdin.read()\n"
        "assert told.startswith('You are the page-transcription stage'), told\n"
        "assert 'Transcribe this scanned page' in told\n"
        f"replies = json.loads({json.dumps(json.dumps(replies))})\n"
        f"reply = replies[os.environ[{key!r}]]\n"
        "time.sleep(60 if reply == 'SLEEP' else 0)\n"
        "sys.stdout.buffer.write(reply.encode())\n"
    )
    script.chmod(0o755)
    if os.name == "nt":
        # Windows starts a script through a command file; the program still reads and writes UTF-8.
        wrapper = tmp_path / f"{name}.cmd"
        wrapper.write_text(f'@"{sys.executable}" -X utf8 "{script}" %*\n')
        return wrapper
    return script


class Provider(BaseHTTPRequestHandler):
    """Stands in for the hosted APIs; the requested model name selects the outcome."""

    seen: list = []

    def log_message(self, *args):
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        headers = {name.lower(): value for name, value in self.headers.items()}
        Provider.seen.append((self.path, headers, body))
        status, extra = 200, {}
        if self.path.startswith("/model/"):
            outcome = self.path.split("/")[2]
            stop = {"ok": "end_turn", "cut": "max_tokens", "refuse": "content_filtered"}
            reply = {
                "output": {
                    "message": {
                        "role": "assistant",
                        "content": [{"reasoningContent": {}}, {"text": "Bedrock read."}],
                    }
                },
                "stopReason": stop.get(outcome),
                "usage": {"inputTokens": 9, "outputTokens": 4},
            }
            if "image" not in body["messages"][0]["content"][0]:
                # The availability check: every model but one answers it.
                reply["stopReason"] = "max_tokens"
                if outcome == "gone":
                    status, reply = 403, {"message": "denied"}
                    extra = {"x-amzn-errortype": "AccessDeniedException:http://internal/"}
        elif self.path == "/v1/messages":
            outcome = body["model"]
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
            outcome = body["model"]
            finish = {"ok": "stop", "cut": "length", "refuse": "content_filter"}[outcome]
            reply = {
                "model": "served-model",
                "choices": [{"finish_reason": finish, "message": {"content": "Endpoint read."}}],
                "usage": {"prompt_tokens": 5, "completion_tokens": 3},
            }
        data = json.dumps(reply).encode()
        self.send_response(status)
        for name, value in extra.items():
            self.send_header(name, value)
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
    assert manifest(out)["vision"]["command"]["name"] == "reader" + SUFFIX
    assert SECRET.encode() not in bundle_bytes(out)


def test_program_output_keeps_one_line_ending(tmp_path, pdf):
    # A program on Windows ends its lines with a carriage return and a line feed.
    replies = {"2": "First line.\r\n\r\nSecond line.\r\n"}
    out = tmp_path / "out"
    program = str(adapter(tmp_path, "reader", replies))
    code, status = job(
        pdf, out, "--vision-provider", "command", "--vision-command", program, "--ocr", "never"
    )
    assert code == 0, status
    assert (out / "pages/000002/vision.md").read_bytes() == b"First line.\n\nSecond line.\n"


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


@pytest.mark.parametrize("kind", ["openai", "anthropic", "bedrock"])
def test_hosted_provider_request_custody_and_typed_refusals(
    tmp_path, pdf, provider, monkeypatch, kind
):
    monkeypatch.setenv("VISION_TEST_KEY", SECRET)
    base = ["--ocr", "never", "--vision-provider", kind, "--vision-base-url", provider]
    base += ["--vision-api-key-env", "VISION_TEST_KEY", "--vision-pages", "2", "--fair-use"]
    base += ["--vision-model"]
    out = tmp_path / "out"
    code, status = job(pdf, out, *base, "ok")
    assert code == 0, status
    path, headers, body = Provider.seen[-1]
    content = body["messages"][-1]["content"]
    if kind == "openai":
        assert path == "/chat/completions" and headers["authorization"] == "Bearer " + SECRET
        image = content[1]["image_url"]["url"].split(",", 1)[1]
        told, expected = body["messages"][0]["content"], "Endpoint read.\n"
    elif kind == "anthropic":
        assert path == "/v1/messages" and headers["x-api-key"] == SECRET
        image = content[0]["source"]["data"]
        told, expected = body["system"], "Claude read.\n"
    else:
        assert path == "/model/ok/converse" and headers["authorization"] == "Bearer " + SECRET
        image = content[0]["image"]["source"]["bytes"]
        told, expected = body["system"][0]["text"], "Bedrock read.\n"
        # The key's access to the model was checked before the page was sent.
        assert [seen[0] for seen in Provider.seen] == [path, path]
        assert Provider.seen[0][2]["inferenceConfig"] == {"maxTokens": 64}
        assert "inferenceConfig" not in body
    assert base64.b64decode(image).startswith(b"\x89PNG")
    assert kind == "bedrock" or body["model"] == "ok"
    # The model is told what the tool is doing and only the declarations the user made.
    assert told.startswith("You are the page-transcription stage")
    assert "fair use" in told and "own work" not in told and "license" not in told
    if kind == "openai":
        monkeypatch.setenv("OPENAI_API_KEY", SECRET)
        unkeyed = ["--ocr", "never", "--vision-provider", kind, "--vision-base-url", provider]
        unkeyed += ["--vision-pages", "2", "--vision-model", "ok", "--own-work", "--under-license"]
        assert job(pdf, tmp_path / "unkeyed", *unkeyed)[0] == 0
        assert "authorization" not in Provider.seen[-1][1]
        other = Provider.seen[-1][2]["messages"][0]["content"]
        assert "own work" in other and "license" in other and "fair use" not in other
        # The recorded digest of the instructions follows the declarations made.
        digests = [manifest(tmp_path / d)["vision"]["prompt_sha256"] for d in ("out", "unkeyed")]
        assert digests[0] != digests[1]
    record = manifest(out)
    assert (out / "pages/000002/vision.md").read_text() == expected
    assert kind == "bedrock" or record["pages"][1]["vision"]["served_model"] == "served-model"
    assert record["vision"]["declarations"] == ["fair_use"]
    assert "vision_api_key_env" not in record["settings"]
    assert b"VISION_TEST_KEY" not in bundle_bytes(out)
    assert SECRET.encode() not in bundle_bytes(out)
    for model, failure in (("cut", "vision-operational"), ("refuse", "vision-refused")):
        target = tmp_path / model
        code, status = job(pdf, target, *base, model)
        assert (code, status["code"], status.get("page")) == (5, failure, 2)
        assert not target.exists() and SECRET not in json.dumps(status)
    # A page the first model fails goes to the second, and the result says so.
    second = tmp_path / "second"
    assert job(pdf, second, *base, "cut", "--vision-fallback-model", "ok")[0] == 0
    read = manifest(second)["pages"][1]["vision"]
    assert read["model"] == "ok"
    assert read["attempts"] == [{"model": "cut", "outcome": "vision-operational"}]
    if kind == "bedrock":
        sent = len(Provider.seen)
        code, status = job(pdf, tmp_path / "gone", *base, "ok", "--vision-fallback-model", "gone")
        assert (code, status["code"], status["page"]) == (5, "vision-operational", None)
        assert "gone is not available" in status["message"]
        assert status["details"] == {"http_status": 403, "error": "AccessDeniedException"}
        # Both models were checked and no page left the machine.
        assert len(Provider.seen) == sent + 2 and not (tmp_path / "gone").exists()


WORDS = " ".join(f"word{n:02d}" for n in range(60))
SUMMARY = "I can't transcribe this page verbatim. Here is a summary: a list of numbered words.\n"


def test_rejected_transcription_falls_back_to_second_model_then_independent_text(tmp_path):
    source = tmp_path / "long.pdf"
    with pymupdf.open() as document:
        document.new_page().insert_textbox(pymupdf.Rect(72, 72, 540, 720), WORDS, fontsize=11)
        with pymupdf.open() as scratch:
            drawn = scratch.new_page()
            drawn.insert_text((72, 100), "Scanned words only.", fontsize=14)
            picture = drawn.get_pixmap(dpi=72)
        document.new_page().insert_image(pymupdf.Rect(0, 0, 612, 792), pixmap=picture)
        document.save(source)
    replies = {"declines": SUMMARY, "reads": WORDS + "\n", "slow": "SLEEP", "sums": "$$x^2$$\n"}
    program = str(adapter(tmp_path, "reader", replies, key="VELLRIC_VISION_MODEL"))
    base = ["--ocr", "never", "--vision-provider", "command", "--vision-command", program]
    first = [*base, "--vision-pages", "1", "--vision-model", "declines"]

    # A reply that shares few words with the page's own text is not kept; the next model is.
    kept = tmp_path / "kept"
    code, status = job(source, kept, *first, "--vision-fallback-model", "reads")
    assert code == 0, status
    page = manifest(kept)["pages"][0]
    assert (kept / page["files"]["vision"]).read_text() == WORDS + "\n"
    assert page["vision"]["model"] == "reads" and page["warnings"] == []
    (attempt,) = page["vision"]["attempts"]
    assert (attempt["model"], attempt["outcome"]) == ("declines", "low-agreement")
    assert attempt["agreement"] < 0.2 and manifest(kept)["vision"]["rejected_pages"] == []
    assert (attempt["vision_words"], attempt["reference_words"]) == (15, 60)

    # A model that overruns the page's time limit has failed the page like any other.
    late = tmp_path / "late"
    slow = [*base, "--vision-pages", "1", "--vision-model", "slow", "--page-timeout-seconds", "1"]
    code, status = job(source, late, *slow, "--vision-fallback-model", "reads")
    assert code == 0, status
    assert manifest(late)["pages"][0]["vision"]["attempts"] == [
        {"model": "slow", "outcome": "deadline"}
    ]

    # Too few prose words beside mathematics is nothing to judge a transcription by.
    sums = tmp_path / "sums"
    assert job(source, sums, *base, "--vision-pages", "1", "--vision-model", "sums")[0] == 0
    assert (sums / "pages/000001/vision.md").read_text() == "$$x^2$$\n"

    # When every model fails the page, the reader view shows the independent reading and says so.
    lost = tmp_path / "lost"
    code, status = job(source, lost, *first, "--vision-fallback-model", "missing")
    assert code == 0, status
    record = manifest(lost)
    page = record["pages"][0]
    assert sorted(page["files"]) == ["native", "text"] and page["vision"]["rejected"] is True
    assert [a["outcome"] for a in page["vision"]["attempts"]] == [
        "low-agreement",
        "vision-operational",
    ]
    assert page["warnings"] and record["vision"]["rejected_pages"] == [1]
    assert record["warnings"] == ["No model transcription was accepted for pages [1]"]
    reader = (lost / "document.md").read_text()
    assert "word59" in reader and "summary" not in reader

    # The floor is the user's to lower.
    lax = tmp_path / "lax"
    assert job(source, lax, *first, "--vision-min-agreement", "0")[0] == 0
    assert (lax / "pages/000001/vision.md").read_text() == SUMMARY

    # A page nothing else has read has no reading to fall back on.
    none = tmp_path / "none"
    alone = [*base, "--vision-pages", "2", "--vision-model", "missing"]
    code, status = job(source, none, *alone, "--vision-fallback-model", "absent")
    assert (code, status["code"], status["page"]) == (5, "vision-operational", 2)
    assert not none.exists()

    # An amend run that leaves the rejected page alone keeps its record and its warning.
    amended = tmp_path / "amended"
    again = [*base, "--vision-pages", "2", "--vision-model", "reads", "--amend", str(lost)]
    code, status = job(source, amended, *again)
    assert code == 0, status
    carried = manifest(amended)["pages"][0]
    assert carried.get("vision") == page["vision"] and carried["warnings"] == page["warnings"]
    assert manifest(amended)["vision"]["rejected_pages"] == [1]


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
    assert record["vision"]["command"]["name"] == "second" + SUFFIX
    assert record["vision"]["pages"] == [1]
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


BEDROCK = ["--vision-provider", "bedrock", "--vision-model", "m"]
REFUSED_SETTINGS = [
    (["--vision-model", "m"], "requires --vision-provider"),
    (["--own-work"], "--own-work requires --vision-provider"),
    (["--vision-region", "us-east-1"], "requires --vision-provider"),
    (BEDROCK, "requires --vision-region"),
    (["--vision-min-agreement", "0.5"], "requires --vision-provider"),
    (
        ["--vision-provider", "openai", "--vision-model", "m", "--vision-region", "us-east-1"],
        "requires the bedrock provider",
    ),
    ([*BEDROCK, "--vision-region", "example.com/x"], "AWS region name"),
    (
        [*BEDROCK, "--vision-region", "us-east-1", "--vision-base-url", "http://localhost:1"],
        "not both",
    ),
    (
        [*BEDROCK, "--vision-base-url", "http://localhost:1"],
        "custom Bedrock endpoint",
    ),
    ([*BEDROCK, "--vision-region", "us-east-1", "--vision-fallback-model", "m"], "different model"),
    (
        ["--vision-provider", "openai", "--vision-model", "m", "--vision-min-agreement", "2"],
        "0..1",
    ),
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


def broker_args(tmp_path, script, *, pass_fds=(), probe=False, pages="2", allow=True):
    settings = tmp_path / "broker.json"
    settings.write_text(
        json.dumps(
            {
                "vellric": {
                    "allow_brokered": allow,
                    "ocr": {"mode": "never", "preflight": "off", "jobs": 3},
                    "vision": {
                        "provider": "bedrock",
                        "region": "us-west-2",
                        "model": "amazon.nova-lite-v1:0",
                        "transport": "command",
                        "probe": probe,
                        "pages": pages,
                        "command": {
                            "argv": [sys.executable, "-I", "-c", script],
                            "pass_fds": pass_fds,
                        },
                        "command_env": ["BROKER_TEST_ALLOWED"],
                        "limits": {
                            "max_concurrency": 1,
                            "max_output_tokens": 9,
                            "max_image_bytes": 4096,
                            "max_image_side_px": 128,
                        },
                    },
                }
            }
        ),
        encoding="utf-8",
    )
    return ["--config", str(settings)]


@pytest.mark.skipif(os.name == "nt", reason="POSIX pass_fds")
@pytest.mark.parametrize("no_probe", [False, True])
def test_broker_fd_custody_through_the_cli(tmp_path, pdf, monkeypatch, no_probe):
    import fcntl

    monkeypatch.setenv("BROKER_TEST_ALLOWED", "synthetic")
    monkeypatch.setenv("BROKER_TEST_EXCLUDED", "sentinel")
    with (tmp_path / "listed").open("w+b") as listed, (tmp_path / "other").open("w+b") as other:
        listed.write(b"listed")
        listed.flush()
        other.write(b"unlisted")
        other.flush()
        selected = fcntl.fcntl(listed, fcntl.F_DUPFD_CLOEXEC, 100)
        excluded = fcntl.fcntl(other, fcntl.F_DUPFD_CLOEXEC, 110)
        script = f"""
import base64, json, os, struct, sys
from pathlib import Path
assert os.pread({selected}, 20, 0) == b'listed'
try:
    assert os.pread({excluded}, 20, 0) != b'unlisted'
except OSError:
    pass
assert os.environ['BROKER_TEST_ALLOWED'] == 'synthetic'
assert 'BROKER_TEST_EXCLUDED' not in os.environ
request = json.load(sys.stdin)
assert set(request) == {{'schema', 'region', 'model', 'body'}}
assert request['schema'] == 'bedrock-converse-request/1'
assert request['region'] == 'us-west-2' and request['model'] == 'amazon.nova-lite-v1:0'
body = request['body']
block = body['messages'][0]['content'][0]
if 'image' in block:
    assert body['inferenceConfig']['maxTokens'] == 9
    picture = block['image']
    data = base64.b64decode(picture['source']['bytes'], validate=True)
    assert len(data) <= 4096
    if picture['format'] == 'png':
        assert max(struct.unpack('>II', data[16:24])) <= 128
    else:
        assert picture['format'] == 'jpeg' and data.startswith(b'\\xff\\xd8')
    event = 'page'
else:
    assert body['inferenceConfig']['maxTokens'] == 64
    assert block == {{'text': 'Reply with the word ready.'}}
    event = 'probe'
with Path({str(tmp_path / "events")!r}).open('a') as log:
    log.write(event + '\\n')
json.dump({{'schema': 'bedrock-converse-response/1', 'status': 'ok', 'body': {{
    'stopReason': 'end_turn', 'output': {{'message': {{
        'role': 'assistant', 'content': [{{'text': 'Recognized text.'}}]
    }}}}
}}}}, sys.stdout)
"""
        try:
            out = tmp_path / "out"
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "vellric",
                    "convert",
                    str(pdf),
                    "--out",
                    str(out),
                    "--status-json",
                    "--progress",
                    "none",
                    *broker_args(tmp_path, script, pass_fds=[selected], probe=True),
                    *(["--no-vision-probe"] if no_probe else []),
                ],
                pass_fds=(selected, excluded),
                capture_output=True,
                text=True,
                timeout=30,
            )
        finally:
            os.close(selected)
            os.close(excluded)
    assert result.returncode == 0, result.stdout + result.stderr
    expected_events = ["page"] if no_probe else ["probe", "page"]
    assert (tmp_path / "events").read_text().splitlines() == expected_events
    assert (out / "pages/000002/vision.md").read_text() == "Recognized text.\n"
    assert b"BROKER_TEST_ALLOWED" not in bundle_bytes(out)


@pytest.mark.skipif(os.name == "nt", reason="POSIX pass_fds")
@pytest.mark.parametrize("allow", [False, True])
def test_broker_refuses_before_input_and_spawn(tmp_path, monkeypatch, capsys, allow):
    def unexpected(*args, **kwargs):
        pytest.fail("input or subprocess accessed with a missing broker descriptor")

    monkeypatch.setattr(cli, "snapshot", unexpected)
    monkeypatch.setattr(cli.subprocess, "Popen", unexpected)
    fstat = os.fstat

    def closed(fd):
        if fd == 255:
            raise OSError("closed")
        return fstat(fd)

    monkeypatch.setattr(cli.os, "fstat", closed)
    assert (
        cli.main(
            [
                "convert",
                "missing.pdf",
                "--out",
                str(tmp_path / "out"),
                "--status-json",
                *broker_args(tmp_path, "raise AssertionError", pass_fds=[255], allow=allow),
            ]
        )
        == 2
    )
    status = json.loads(capsys.readouterr().out)
    assert status["stage"] == "settings"
    assert status["message"] == (
        "A required broker descriptor is closed"
        if allow
        else "Bedrock command transport requires allow_brokered"
    )


@pytest.mark.skipif(os.name == "nt", reason="POSIX process groups")
@pytest.mark.parametrize("probe", [False, True])
def test_broker_failure_never_uses_cloud(tmp_path, monkeypatch, probe):
    def unexpected(*args, **kwargs):
        pytest.fail("broker failure attempted a cloud transport")

    monkeypatch.setattr(vision, "_post", unexpected)
    monkeypatch.setattr(vision, "signing_credentials", unexpected)
    script = """import json, sys
json.load(sys.stdin)
json.dump({'schema': 'bedrock-converse-response/1', 'status': 'error',
           'category': 'throttled'}, sys.stdout)
"""
    settings = {
        "provider": "bedrock",
        "transport": "command",
        "region": "us-west-2",
        "model": "amazon.nova-lite-v1:0",
        "max_output_tokens": 5,
        "limits": {},
        "command": {"argv": [sys.executable, "-I", "-c", script], "pass_fds": []},
        "declarations": [],
        "env": {},
    }
    picture = tmp_path / "page.png"
    Image.new("RGB", (8, 8)).save(picture)
    with pytest.raises(JobError) as caught:
        if probe:
            vision.probe(settings, timeout=5, temp=tmp_path)
        else:
            vision.transcribe(picture, 1, settings, timeout=5, temp=tmp_path)
    assert caught.value.code == "vision-operational"
    assert caught.value.details == {"category": "throttled"}


@pytest.mark.parametrize(
    "raw",
    [
        b"\xff",
        b"{}{}",
        b'{"schema":"bedrock-converse-response/1","status":"error","category":"refused","text":"x"}',
        b'{"schema":"bedrock-converse-response/1","status":"ok","body":{"stopReason":"end_turn"}}',
    ],
)
def test_broker_rejects_malformed_response(raw):
    with pytest.raises(JobError) as caught:
        broker.decode(raw, 1)
    assert caught.value.details == {"category": "invalid"}


def test_bedrock_image_respects_encoded_bytes_and_dimensions(tmp_path):
    picture = tmp_path / "page.png"
    Image.new("RGB", (100, 64), "red").save(picture)
    kind, payload = vision._bedrock_image(
        picture, {"max_image_bytes": 1000, "max_image_side_px": 32}, 1
    )
    assert kind == "jpeg" and len(payload) <= 1000
    with pytest.raises(JobError, match="exceeds"):
        vision._bedrock_image(picture, {"max_image_bytes": 1}, 1)


@pytest.mark.skipif(os.name == "nt", reason="POSIX process groups")
def test_broker_timeout_kills_descendants(tmp_path):
    read_fd, write_fd = os.pipe()
    script = f"""
import json, os, sys, time
json.load(sys.stdin)
if os.fork() == 0:
    os.write({write_fd}, b'alive')
time.sleep(60)
"""
    settings = {
        "region": "us-west-2",
        "model": "amazon.nova-lite-v1:0",
        "env": {},
        "command": {"argv": [sys.executable, "-I", "-c", script], "pass_fds": [write_fd]},
    }
    try:
        with pytest.raises(JobError) as caught:
            broker.converse(settings, {}, 1, 1.5, tmp_path, None)
        assert caught.value.details == {"category": "unavailable"}
        os.close(write_fd)
        write_fd = None
        assert select.select([read_fd], [], [], 2)[0] == [read_fd]
        assert os.read(read_fd, 10) == b"alive"
        assert select.select([read_fd], [], [], 2)[0] == [read_fd]
        assert os.read(read_fd, 10) == b""
    finally:
        os.close(read_fd)
        if write_fd is not None:
            os.close(write_fd)


@pytest.mark.skipif(os.name == "nt", reason="POSIX process groups")
def test_broker_stdout_limit_is_enforced(tmp_path, monkeypatch):
    monkeypatch.setattr(broker, "RESPONSE_LIMIT", 64)
    settings = {
        "region": "us-west-2",
        "model": "amazon.nova-lite-v1:0",
        "env": {},
        "command": {
            "argv": [sys.executable, "-I", "-c", "import sys; sys.stdin.read(); print('x' * 65)"],
            "pass_fds": [],
        },
    }
    with pytest.raises(JobError) as caught:
        broker.converse(settings, {}, 1, 5, tmp_path, None)
    assert caught.value.details == {"category": "limit"}


@pytest.mark.skipif(os.name == "nt", reason="POSIX process groups")
def test_broker_concurrency_caps_page_jobs(tmp_path, pdf):
    script = """
import fcntl, json, sys, time
with open('helper-lock', 'a') as lock:
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    assert 'image' in json.load(sys.stdin)['body']['messages'][0]['content'][0]
    time.sleep(0.15)
    json.dump({'schema': 'bedrock-converse-response/1', 'status': 'ok', 'body': {
        'stopReason': 'end_turn', 'output': {'message': {
            'role': 'assistant', 'content': [{'text': 'Recognized text.'}],
        }},
    }}, sys.stdout)
"""
    out = tmp_path / "out"
    code, status = job(pdf, out, *broker_args(tmp_path, script, pages="1-3"))
    assert code == 0, status
    assert len(list(out.glob("pages/*/vision.md"))) == 3


def test_sigv4_signs_only_the_selected_bedrock_request(tmp_path, monkeypatch):
    pytest.importorskip("botocore")

    def post(url, body, headers, page, timeout):
        assert url == (
            "https://bedrock-runtime.us-west-2.amazonaws.com/model/amazon.nova-lite-v1%3A0/converse"
        )
        assert "/us-west-2/bedrock/aws4_request" in headers["Authorization"]
        assert headers["X-Amz-Security-Token"] == "test-session-token"
        assert json.loads(body)["inferenceConfig"] == {"maxTokens": 5}
        return {}

    monkeypatch.setattr(vision, "_post", post)
    assert (
        vision._converse(
            {
                "region": "us-west-2",
                "model": "amazon.nova-lite-v1:0",
                "transport": "sigv4",
                "base_url": "https://bedrock-runtime.us-west-2.amazonaws.com",
                "sigv4": ["test-key", "test-secret", "test-session-token"],
                "max_output_tokens": 5,
            },
            {"messages": []},
            1,
            2,
            temp=tmp_path,
        )
        == {}
    )


def test_markdown_command_receives_only_allowlisted_caller_variables(tmp_path, pdf, monkeypatch):
    monkeypatch.setenv("VELLRIC_TEST_COMMAND_ENV_ALLOWED", "accepted")
    monkeypatch.setenv("VELLRIC_TEST_COMMAND_ENV_DENIED", "excluded")
    executable = adapter(
        tmp_path,
        "allowlisted",
        {"accepted": "Filtered environment."},
        key="VELLRIC_TEST_COMMAND_ENV_ALLOWED",
    )
    out = tmp_path / "out"
    code, status = job(
        pdf,
        out,
        "--vision-provider",
        "command",
        "--vision-command",
        str(executable),
        "--vision-command-env",
        "VELLRIC_TEST_COMMAND_ENV_ALLOWED",
        "--vision-pages",
        "2",
        "--ocr",
        "never",
    )
    assert code == 0, status
    assert (out / "pages/000002/vision.md").read_text() == "Filtered environment.\n"


@pytest.mark.skipif(os.name == "nt", reason="POSIX executable alias")
def test_broker_preserves_configured_executable_alias(tmp_path):
    alias = tmp_path / "venv-python"
    alias.symlink_to(sys.executable)
    config = tmp_path / "alias.json"
    config.write_text(
        json.dumps(
            {
                "vellric": {
                    "allow_brokered": True,
                    "vision": {
                        "provider": "bedrock",
                        "transport": "command",
                        "region": "us-west-2",
                        "model": "amazon.nova-lite-v1:0",
                        "command": {"argv": [str(alias)]},
                    },
                }
            }
        ),
        encoding="utf-8",
    )
    options = vars(
        cli.parser().parse_args(
            [
                "convert",
                "input",
                "--out",
                "out",
                "--config",
                str(config),
            ]
        )
    )
    cli.validate_options(options)
    assert options["vision_command"]["argv"][0] == str(alias)


def test_reaping_ignores_missing_or_foreign_broker_groups(tmp_path, monkeypatch):
    for group in (101, 102, 103):
        (tmp_path / f".broker-{group}").touch()
    monkeypatch.setattr(
        broker, "group_alive", lambda group, session: (group, session) == (102, 101)
    )
    killed = []
    monkeypatch.setattr(broker, "kill_group", killed.append)
    broker.reap_groups(tmp_path, 101)
    assert killed == [102]


def test_macos_broker_watchdog_counts_owned_subgroups(tmp_path, monkeypatch):
    monkeypatch.setattr(cli.sys, "platform", "darwin")
    monkeypatch.setattr(cli, "group_rss", {10: 100, 11: 250, 12: 50}.__getitem__)

    def active_groups(work, session):
        assert (work, session) == (tmp_path, 10)
        return iter((11, 12))

    monkeypatch.setattr(broker, "active_groups", active_groups)
    assert cli.supervised_rss(10, tmp_path, brokered=True) == 400
    assert cli.supervised_rss(10, tmp_path, brokered=False) == 100


def test_broker_observation_errors_report_dependency_unavailable(tmp_path, monkeypatch):
    def denied(*args):
        raise OSError("synthetic observer failure")

    monkeypatch.setattr(cli.sys, "platform", "darwin")
    monkeypatch.setattr(cli, "group_rss", lambda group: 100)
    monkeypatch.setattr(broker, "active_groups", denied)
    with pytest.raises(JobError) as caught:
        cli.supervised_rss(10, tmp_path, brokered=True)
    assert (caught.value.code, caught.value.stage) == ("dependency-unavailable", "supervision")

    process = Mock(pid=100)
    process.poll.return_value = 0
    monkeypatch.setattr(broker, "group_alive", denied)
    monkeypatch.setattr(broker.subprocess, "Popen", lambda *args, **kwargs: process)
    monkeypatch.setattr(broker, "exchange", lambda *args: b"{}")
    marker = tmp_path / ".broker-100"
    marker.touch()
    settings = {
        "region": "us-west-2",
        "model": "amazon.nova-lite-v1:0",
        "env": {},
        "command": {"argv": [sys.executable], "pass_fds": []},
    }
    with pytest.raises(JobError) as caught:
        broker.converse(settings, {}, 1, 1, tmp_path, None)
    assert (caught.value.code, caught.value.stage) == ("dependency-unavailable", "vision")
    process.wait.assert_called_once()
    process.stdin.close.assert_called_once()
    process.stdout.close.assert_called_once()
    assert marker.exists()


@pytest.mark.skipif(os.name == "nt", reason="POSIX process groups")
@pytest.mark.parametrize("worker_succeeds", [True, False])
def test_broker_reap_failure_preserves_publication_boundary(
    tmp_path, pdf, monkeypatch, capsys, worker_succeeds
):
    response = {"schema": "bedrock-converse-response/1"}
    if worker_succeeds:
        response.update(
            status="ok",
            body={
                "stopReason": "end_turn",
                "output": {"message": {"role": "assistant", "content": [{"text": "Read."}]}},
            },
        )
    else:
        response.update(status="error", category="refused")
    script = f"import sys; sys.stdin.read(); print({json.dumps(response)!r})"
    calls = []

    def denied(work, group):
        calls.append(group)
        raise OSError("synthetic broker observation fault")

    monkeypatch.setattr(cli, "supervised_rss", lambda *args, **kwargs: 0)
    monkeypatch.setattr(broker, "active_groups", denied)
    out = tmp_path / "out"
    result = cli.main(
        [
            "convert",
            str(pdf),
            "--out",
            str(out),
            "--status-json",
            "--progress",
            "none",
            *broker_args(tmp_path, script),
        ]
    )
    assert result != 0
    status = json.loads(capsys.readouterr().out)
    expected = (
        ("dependency-unavailable", "supervision")
        if worker_succeeds
        else (
            "vision-refused",
            "vision",
        )
    )
    assert (status["code"], status["stage"]) == expected
    assert calls and not out.exists()
    assert not list(tmp_path.glob(".out.vellric-*"))


def test_signing_credentials_only_wraps_expected_provider_failures(monkeypatch):
    session = pytest.importorskip("botocore.session")
    exceptions = pytest.importorskip("botocore.exceptions")
    get_credentials = Mock(side_effect=exceptions.ProfileNotFound(profile="synthetic"))
    monkeypatch.setattr(session, "Session", lambda: Mock(get_credentials=get_credentials))
    with pytest.raises(JobError, match="signing credentials are unavailable"):
        vision.signing_credentials(explicit_config=False)
    get_credentials.side_effect = RuntimeError("synthetic programming error")
    with pytest.raises(RuntimeError, match="synthetic programming error"):
        vision.signing_credentials(explicit_config=False)
