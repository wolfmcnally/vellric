"""Standalone complete PDF jobs with a supervising process and private artifacts."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import importlib.util
import json
import os
import re
import select
import signal
import stat
import subprocess
import sys
import tempfile
import threading
import time
import urllib.parse
from collections.abc import Sequence
from pathlib import Path

from . import __version__, vision
from .runtime import (
    BEHAVIOR,
    SCHEMA,
    STATUS_SCHEMA,
    SUPERVISED,
    WINDOWS,
    JobError,
    contain,
    digest,
    environment,
    find_program,
    group_rss,
    kill_group,
    private_directory,
    publication_available,
    publish,
    remove_tree,
    tree_size,
    validate_bundle,
    write_json,
)


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise JobError("usage", message, stage="settings")


def parser() -> argparse.ArgumentParser:
    p = Parser(
        prog="vellric", description="Local PDF inspection, fidelity conversion, rendering and OCR."
    )
    p.add_argument("--version", action="version", version=f"vellric {__version__}")
    commands = p.add_subparsers(dest="command")
    doctor = commands.add_parser("doctor")
    doctor.add_argument("--json", action="store_true")
    doctor.add_argument("--language", default="eng")
    doctor.add_argument("--tessdata-dir")
    for name in ("inspect", "convert", "render", "image"):
        c = commands.add_parser(name)
        c.add_argument("input")
        c.add_argument("--out", required=True)
        c.add_argument("--schema", choices=["1"], default="1")
        c.add_argument("--expected-sha256")
        c.add_argument("--status-json", action="store_true")
        c.add_argument("--progress", choices=["human", "json", "none"], default="human")
        c.add_argument("--timeout-seconds", type=float, default=3600)
        c.add_argument("--page-timeout-seconds", type=float, default=300)
        c.add_argument("--memory-mib", type=int, default=2048)
        c.add_argument("--max-raster-bytes", type=int, default=256 * 1024 * 1024)
        c.add_argument("--max-input-bytes", type=int, default=512 * 1024 * 1024)
        c.add_argument("--max-output-bytes", type=int, default=2 * 1024 * 1024 * 1024)
        c.add_argument("--max-pages", type=int, default=10000)
        c.add_argument("--temp-dir")
        c.add_argument("--tessdata-dir")
        c.add_argument("--layout", action="store_true")
        c.add_argument("--raster-threshold", type=float, default=0.5)
        c.add_argument("--dpi", type=float, default=300)
        c.add_argument("--title")
        passwords = c.add_mutually_exclusive_group()
        passwords.add_argument("--password-file")
        passwords.add_argument("--password-stdin", action="store_true")
        c.set_defaults(
            ocr="never",
            preflight="off",
            structure="none",
            jobs=1,
            language="eng",
            searchable_pdf=False,
            diagnostics=False,
            ocr_pages=None,
            rotate_threshold=2.0,
            preflight_timeout_seconds=1800.0,
        )
        if name == "convert":
            c.add_argument("--ocr", choices=["auto", "never", "always"], default="auto")
            c.add_argument("--preflight", choices=["on", "off"], default="on")
            c.add_argument("--structure", choices=["none", "native"], default="none")
            c.add_argument(
                "--ocr-pages", help="explicit recognition pages/ranges in a complete document job"
            )
            c.add_argument("--rotate-threshold", type=float, default=2.0)
            c.add_argument("--preflight-timeout-seconds", type=float, default=1800.0)
            c.add_argument("--jobs", type=int, default=1)
            c.add_argument("--language", default="eng")
            c.add_argument("--searchable-pdf", action="store_true")
            c.add_argument("--diagnostics", action="store_true")
            c.add_argument(
                "--vision-provider",
                choices=list(vision.PROVIDERS),
                help="opt in to a high-quality pass by a vision-capable model",
            )
            c.add_argument("--vision-model", help="model name as the provider knows it")
            c.add_argument("--vision-base-url", help="endpoint for a hosted provider")
            c.add_argument("--vision-region", help="AWS region for --vision-provider bedrock")
            c.add_argument(
                "--vision-fallback-model", help="second model tried on a page the first fails"
            )
            c.add_argument("--vision-min-agreement", type=float)
            c.add_argument(
                "--own-work", action="store_true", help="tell the model the document is your own"
            )
            c.add_argument(
                "--under-license",
                action="store_true",
                help="tell the model you hold a license to copy the document",
            )
            c.add_argument(
                "--fair-use", action="store_true", help="tell the model your use is fair use"
            )
            c.add_argument(
                "--vision-api-key-env", help="name of the environment variable holding the key"
            )
            c.add_argument("--vision-command", help="program for --vision-provider command")
            c.add_argument("--vision-pages", help="pages/ranges that receive the vision pass")
            c.add_argument("--vision-cross-check", choices=["on", "off"], default="on")
            c.add_argument("--vision-max-side", type=int, default=vision.DEFAULT_MAX_SIDE)
            c.add_argument("--vision-max-output-tokens", type=int)
            c.add_argument(
                "--amend", help="earlier convert result of this input whose other pages are kept"
            )
        if name == "image":
            c.add_argument("--width", type=int)
            c.add_argument("--height", type=int)
        if name == "render":
            c.add_argument("--pages")
            c.add_argument("--subset-pdf", action="store_true")
            c.add_argument("--pixel-fingerprints", action="store_true")
            c.add_argument("--format", choices=["png", "pnm", "jpeg"], default="png")
            c.add_argument("--rotation", type=int, choices=[0, 90, 180, 270], default=0)
            c.add_argument("--clip")
            c.add_argument("--colorspace", choices=["rgb", "gray"], default="rgb")
            c.add_argument("--strips", action="store_true")
            c.add_argument("--strip-pixels", type=int, default=8000)
            c.add_argument("--max-side", type=int)
            c.add_argument("--jpeg-quality", type=int, default=85)
    return p


def doctor(
    *, language: str = "eng", tessdata_dir: str | None = None, include_osd: bool = True
) -> dict:
    publication = publication_available()
    data = {
        "tool": {"name": "vellric", "version": __version__},
        "schema": SCHEMA,
        "behavior": BEHAVIOR,
        "platform": sys.platform,
        "license": "AGPL-3.0-only",
        "enforcement": {
            "memory": "process-group RSS watchdog; can overshoot",
            "rss_available": WINDOWS
            or (
                Path("/proc").is_dir()
                if sys.platform.startswith("linux")
                else Path("/bin/ps").is_file()
            ),
            "disk": "private-workspace watchdog; can overshoot",
            "raster": "pre-render byte admission",
            "publication": "exclusive atomic rename available"
            if publication
            else "unavailable; jobs refuse",
            "hard_sandbox": False,
        },
        "engines": {},
        "language_data": [],
    }
    for package in ("pymupdf", "ocrmypdf"):
        try:
            data["engines"][package] = {"version": importlib.metadata.version(package)}
        except importlib.metadata.PackageNotFoundError:
            data["engines"][package] = {"available": False}

    def probe(executable, argument, temp):
        try:
            result = subprocess.run(
                [executable, argument],
                capture_output=True,
                text=True,
                timeout=15,
                env=environment(temp, tessdata_dir),
            )
            return result.returncode, result.stdout or result.stderr
        except (OSError, subprocess.TimeoutExpired, UnicodeError):
            return None, ""

    tessdata = None
    for tool in ("tesseract", "ocrmypdf", "gs"):
        # Ghostscript's console program has its own name on Windows.
        name = "gswin64c" if WINDOWS and tool == "gs" else tool
        executable = find_program(name, path=environment(Path(tempfile.gettempdir()))["PATH"])
        entry = {"available": False}
        if executable:
            with tempfile.TemporaryDirectory(prefix="vellric-doctor-") as temp:
                returncode, output = probe(executable, "--version", Path(temp))
                lines = output.splitlines()
                entry["returncode"] = returncode
                entry["available"] = returncode == 0 and bool(lines)
                if entry["available"]:
                    entry["version"] = lines[0][:200]
                    entry["executable_sha256"] = digest(Path(executable).resolve())
                if tool == "tesseract" and entry["available"]:
                    rc, listing = probe(executable, "--list-langs", Path(temp))
                    match = re.search(r'List of available languages in "([^"]+)"', listing)
                    if rc == 0:
                        tessdata = (
                            Path(tessdata_dir)
                            if tessdata_dir
                            else Path(match[1])
                            if match
                            else None
                        )
        data["engines"][tool] = entry
    requested = set(language.split("+")) | ({"osd"} if include_osd else set())
    missing = []
    for name in sorted(requested):
        # Language identifiers cannot escape the selected data directory.
        path = (
            tessdata / (name + ".traineddata")
            if tessdata and re.fullmatch(r"[A-Za-z0-9_.-]+", name)
            else None
        )
        if path and path.is_file():
            data["language_data"].append({"name": path.name, "sha256": digest(path)})
        else:
            missing.append(name)
    data["missing_languages"] = missing
    return data


def validate_options(options: dict) -> None:
    for key in (
        "timeout_seconds",
        "page_timeout_seconds",
        "preflight_timeout_seconds",
        "memory_mib",
        "max_raster_bytes",
        "max_input_bytes",
        "max_output_bytes",
        "max_pages",
        "dpi",
        "jobs",
    ):
        value = options[key]
        if not value > 0 or value == float("inf"):
            raise JobError(
                "usage", f"{key.replace('_', '-')} must be finite and positive", stage="settings"
            )
    if not 0 <= options["rotate_threshold"] < float("inf"):
        raise JobError("usage", "rotate-threshold must be finite and nonnegative", stage="settings")
    if options["ocr_pages"] is not None and options["ocr"] != "auto":
        raise JobError("usage", "Explicit OCR pages require --ocr auto", stage="settings")
    for key in ("temp_dir", "tessdata_dir"):
        if options.get(key):
            try:
                directory = Path(options[key]).resolve(strict=True)
                if not directory.is_dir():
                    raise ValueError
            except (OSError, ValueError) as exc:
                raise JobError(
                    "usage",
                    f"{key.replace('_', '-')} must be an existing directory",
                    stage="settings",
                ) from exc
            options[key] = str(directory)
    if not 0 < options["raster_threshold"] <= 1:
        raise JobError("usage", "Invalid raster threshold")
    if options["password_stdin"] and options["input"] == "-":
        raise JobError("usage", "Input and password cannot both use stdin")
    if options["searchable_pdf"] and (options["preflight"] != "on" or options["ocr"] == "never"):
        raise JobError("usage", "Searchable PDF requires preflight and OCR auto or always")
    if options["expected_sha256"] and not re.fullmatch(
        "[0-9a-fA-F]{64}", options["expected_sha256"]
    ):
        raise JobError("usage", "Expected SHA-256 must have 64 hexadecimal digits")
    if not re.fullmatch("[A-Za-z0-9_+.-]+", options["language"]):
        raise JobError("usage", "Invalid OCR language")
    if options.get("clip"):
        try:
            options["clip"] = [float(v) for v in options["clip"].split(",")]
            if len(options["clip"]) != 4 or any(
                not float("-inf") < v < float("inf") for v in options["clip"]
            ):
                raise ValueError
        except ValueError as exc:
            raise JobError("usage", "Clip requires four finite coordinates") from exc
    if options.get("strip_pixels", 1) <= 0 or (
        options.get("max_side") is not None and options["max_side"] <= 0
    ):
        raise JobError("usage", "Invalid render limit")
    if options.get("pixel_fingerprints") and (
        options["dpi"] != 144
        or options.get("rotation") != 0
        or options.get("colorspace") != "rgb"
        or options.get("clip")
        or options.get("strips")
        or options.get("max_side")
        or options.get("format") == "jpeg"
    ):
        raise JobError("usage", "Canonical page fingerprints require full RGB pages at 144 DPI")
    if options["command"] == "image":
        width, height = options.get("width"), options.get("height")
        if (width is None) != (height is None) or any(
            type(n) is not int or n <= 0 or n > 30000 for n in (width, height) if n is not None
        ):
            raise JobError("usage", "Image resize requires positive width and height <=30000")
    if not 1 <= options.get("jpeg_quality", 85) <= 100:
        raise JobError("usage", "JPEG quality must be 1..100")
    validate_vision(options)


def validate_vision(options: dict) -> None:
    """Vision and amend settings exist on convert only; refuse every contradiction up front."""
    provider = options.get("vision_provider")
    if provider is None:
        named = [
            key
            for key in (
                "vision_model",
                "vision_base_url",
                "vision_region",
                "vision_fallback_model",
                "vision_min_agreement",
                "vision_api_key_env",
                "vision_command",
                "vision_pages",
                "vision_max_output_tokens",
                "amend",
            )
            if options.get(key) is not None
        ] + [key for key in vision.DECLARATIONS if options.get(key)]
        if named:
            raise JobError(
                "usage",
                f"--{named[0].replace('_', '-')} requires --vision-provider",
                stage="settings",
            )
        return

    def refuse(message: str) -> JobError:
        return JobError("usage", message, stage="settings")

    if not 256 <= options["vision_max_side"] <= 30000:
        raise refuse("vision-max-side must be 256..30000")
    tokens = options["vision_max_output_tokens"]
    if tokens is not None and not 1 <= tokens <= 1_000_000:
        raise refuse("vision-max-output-tokens must be positive")
    if options["vision_min_agreement"] is None:
        options["vision_min_agreement"] = vision.DEFAULT_MIN_AGREEMENT
    if not 0.0 <= options["vision_min_agreement"] <= 1.0:
        raise refuse("vision-min-agreement must be 0..1")
    fallback = options["vision_fallback_model"]
    if fallback is not None and (not fallback or fallback == options["vision_model"]):
        raise refuse("vision-fallback-model must name a different model")
    region = options["vision_region"]
    if region is not None and provider != "bedrock":
        raise refuse("vision-region requires the bedrock provider")
    if provider == "bedrock" and (region is None) == (options["vision_base_url"] is None):
        raise refuse("The bedrock provider requires --vision-region or --vision-base-url, not both")
    if region is not None and not re.fullmatch("[a-z]{2,5}(-[a-z]+)+-[0-9]+", region):
        raise refuse("vision-region must be an AWS region name")
    if options["searchable_pdf"] and options["vision_cross_check"] == "off":
        # Skipping Tesseract for vision pages would leave them out of the searchable derivative.
        raise refuse("Searchable PDF requires --vision-cross-check on")
    if provider == "command":
        if options["vision_base_url"] or options["vision_api_key_env"] or tokens is not None:
            raise refuse("The command provider takes no base URL, API key or token limit")
        try:
            command = Path(options["vision_command"] or "").resolve(strict=True)
            if not command.is_file() or not os.access(command, os.X_OK):
                raise ValueError
        except (OSError, ValueError) as exc:
            raise refuse("vision-command must name an executable file") from exc
        options["vision_command"] = str(command)
    else:
        if options["vision_command"]:
            raise refuse("vision-command requires the command provider")
        if not options["vision_model"]:
            raise refuse("This vision provider requires --vision-model")
        default_url = (
            vision.bedrock_url(region) if region else vision.DEFAULT_BASE_URL.get(provider)
        )
        url = options["vision_base_url"] or default_url
        try:
            parts = urllib.parse.urlsplit(url)
            valid = (
                parts.scheme in ("http", "https")
                and bool(parts.hostname)
                and "@" not in parts.netloc
                and (parts.port is None or parts.port > 0)
            )
        except ValueError:
            valid = False
        if not valid:
            raise refuse("vision-base-url must be an http(s) URL without credentials")
        options["vision_base_url"] = url
        name = options["vision_api_key_env"]
        if name is not None and not re.fullmatch("[A-Za-z_][A-Za-z0-9_]*", name):
            raise refuse("Invalid API key variable name")
        # A key goes only where the user sent it: the provider's own endpoint takes the
        # provider's usual variable, and any other endpoint takes a key only when one is named.
        if name is None and url == default_url:
            name = options["vision_api_key_env"] = vision.DEFAULT_KEY_ENV[provider]
        if name is None and provider != "openai":
            raise refuse(f"A custom {provider.capitalize()} endpoint requires --vision-api-key-env")
        if name is not None and not os.environ.get(name):
            raise refuse(f"Environment variable {name} holds no API key")
        if provider == "anthropic" and importlib.util.find_spec("anthropic") is None:
            raise JobError(
                "dependency-unavailable",
                "The anthropic provider requires the vision extra: install vellric[vision]",
                stage="settings",
            )
    if options["amend"] is not None:
        if options["vision_pages"] is None:
            raise refuse("--amend requires --vision-pages")
        if options["searchable_pdf"] or options["diagnostics"] or options["ocr_pages"] is not None:
            raise refuse("--amend cannot be combined with searchable PDF, diagnostics or OCR pages")
        try:
            prior = Path(options["amend"]).resolve(strict=True)
            if not (prior / "manifest.json").is_file():
                raise ValueError
        except (OSError, ValueError) as exc:
            raise refuse("--amend must name an earlier convert result directory") from exc
        if prior in Path(options["out"]).absolute().parents:
            raise refuse("--out must lie outside the --amend directory")
        options["amend"] = str(prior)
        # An amend run recognises nothing itself: every other page is carried forward.
        options["ocr"], options["preflight"] = "never", "off"


def vision_settings(options: dict) -> dict | None:
    """What the worker needs to reach the provider, including material no artifact may carry."""
    provider = options.get("vision_provider")
    if provider is None:
        return None
    settings = {
        "provider": provider,
        "model": options["vision_model"],
        "fallback_model": options["vision_fallback_model"],
        "declarations": [name for name in vision.DECLARATIONS if options[name]],
        "base_url": options["vision_base_url"],
        "max_output_tokens": options["vision_max_output_tokens"]
        or (vision.ANTHROPIC_MAX_OUTPUT_TOKENS if provider == "anthropic" else None),
    }
    if provider == "command":
        # The user's own program runs as the user would run it.
        settings |= {"command": options["vision_command"], "env": dict(os.environ)}
    elif options["vision_api_key_env"]:
        settings["api_key"] = os.environ[options["vision_api_key_env"]]
    return settings


def read_within(descriptor: int, size: int, remaining: float) -> bytes | None:
    """One read of a stream that may never deliver; None once ``remaining`` seconds pass."""
    if not WINDOWS:
        if remaining <= 0 or not select.select([descriptor], [], [], remaining)[0]:
            return None
        return os.read(descriptor, size)
    # Windows cannot wait on a pipe or a console, so the read waits on a thread of its own.
    box = []

    def read():
        try:
            box.append(os.read(descriptor, size))
        except OSError:
            box.append(b"")

    reader = threading.Thread(target=read, daemon=True)
    reader.start()
    deadline = time.monotonic() + remaining
    while reader.is_alive() and time.monotonic() < deadline:
        reader.join(0.05)  # Short waits let a cancellation signal be handled between them.
    return box[0] if box else None


def open_input(name: str):
    """The named regular file itself, never what a link stands for."""
    if not WINDOWS:
        fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    else:
        named = os.lstat(name)
        if not stat.S_ISREG(named.st_mode) or Path(name).is_junction():
            raise OSError("not regular")
        fd = os.open(name, os.O_RDONLY | getattr(os, "O_BINARY", 0))
        if not os.path.samestat(named, os.fstat(fd)):  # The name was swapped for a link.
            os.close(fd)
            raise OSError("not regular")
    if not stat.S_ISREG(os.fstat(fd).st_mode):
        os.close(fd)
        raise OSError("not regular")
    return os.fdopen(fd, "rb")


def snapshot(options: dict, work: Path) -> tuple[Path, str, int]:
    source = work / "source.pdf"
    hashed = hashlib.sha256()
    size = 0
    if options["input"] == "-":
        stream = sys.stdin.buffer
        close = False
    else:
        try:
            stream = open_input(options["input"])
            close = True
        except OSError as exc:
            raise JobError(
                "pdf-open-operational", "Input must be an accessible regular file; symlinks refused"
            ) from exc
    started = time.monotonic()

    def blocks():
        while True:
            remaining = options["timeout_seconds"] - (time.monotonic() - started)
            if remaining <= 0:
                raise JobError("deadline", "Input snapshot deadline exceeded", stage="snapshot")
            if options["input"] == "-":
                block = read_within(stream.fileno(), 1024 * 1024, remaining)
                if block is None:
                    raise JobError("deadline", "Input stream deadline exceeded", stage="snapshot")
            else:
                block = stream.read(1024 * 1024)
            if not block:
                break
            yield block

    try:
        with source.open("wb") as output:
            for block in blocks():
                size += len(block)
                if size > options["max_input_bytes"]:
                    raise JobError("resource-limit", "Input exceeds byte limit", stage="snapshot")
                output.write(block)
                hashed.update(block)
    finally:
        if close:
            stream.close()
    identity = hashed.hexdigest()
    if options["expected_sha256"] and identity != options["expected_sha256"].lower():
        raise JobError(
            "source-hash-mismatch", "Input bytes differ from expected SHA-256", stage="snapshot"
        )
    return source, identity, size


def run_job(options: dict) -> dict:
    previous = {}

    def cancelled(signum, frame):
        raise JobError("deadline", "Job cancelled", stage="supervision", details={"signal": signum})

    try:
        # Windows delivers a parent's request to stop as a break event.
        for sig in (signal.SIGINT, signal.SIGTERM, *([signal.SIGBREAK] if WINDOWS else [])):
            previous[sig] = signal.signal(sig, cancelled)
        return _run_job(options)
    finally:
        for sig, handler in previous.items():
            signal.signal(sig, handler)


def _run_job(options: dict) -> dict:
    validate_options(options)
    if WINDOWS and sys.version_info < (3, 12, 4):
        # Earlier releases create the private workspace readable by other accounts.
        raise JobError(
            "dependency-unavailable", "Windows requires Python 3.12.4 or later", stage="settings"
        )
    job_started = time.monotonic()
    requested = Path(options["out"]).absolute()
    parent = requested.parent.resolve(strict=True)
    target = parent / requested.name
    if target.exists() or target.is_symlink():
        raise JobError("artifact-invalid", "Destination already exists", stage="publication")
    temp_base = Path(options["temp_dir"]).resolve(strict=True) if options["temp_dir"] else None
    with private_directory("vellric-job-", temp_base) as temp:
        work = Path(temp).resolve()
        os.chmod(work, 0o700)
        password = ""
        if options["password_file"]:
            with open(options["password_file"], "rb") as f:
                raw = f.read(4097)
            if len(raw) > 4096:
                raise JobError("usage", "Password input exceeds 4096 bytes")
            password = raw.decode("utf-8").rstrip("\r\n")
        elif options["password_stdin"]:
            raw = bytearray()
            while not raw.endswith(b"\n"):
                remaining = options["timeout_seconds"] - (time.monotonic() - job_started)
                chunk = read_within(sys.stdin.fileno(), 1, remaining)
                if chunk is None:
                    raise JobError("deadline", "Password input deadline exceeded", stage="snapshot")
                if not chunk:
                    break
                raw.extend(chunk)
                if len(raw) > 4096:
                    raise JobError("usage", "Password input exceeds 4096 bytes")
            password = raw.decode("utf-8").rstrip("\r\n")
        source, identity, size = snapshot(options, work)
        staging = None
        process = None
        group = None
        try:
            staging = Path(tempfile.mkdtemp(prefix=f".{target.name}.vellric-", dir=parent))
            os.chmod(staging, 0o700)
            title = (
                re.sub(r"[^a-z0-9]+", " ", Path(options["input"]).stem.lower()).strip().title()
                or "Document"
            )
            config = {
                "options": options,
                "source": str(source),
                "sha256": identity,
                "size": size,
                "staging": str(staging),
                "work": str(work),
                "result": str(work / "result.json"),
                "password": password,
                "title": title,
                "vision": options.get("vision_provider") is not None,
            }
            write_json(work / "config.json", config)
            os.chmod(work / "config.json", 0o600)
            # Execute the installed package entry in isolation. The private
            # bootstrap names only this package root.
            bootstrap = (
                "import sys;sys.path.insert(0,sys.argv.pop(1));"
                "from vellric.worker import main;raise SystemExit(main())"
            )
            package_root = str(Path(__file__).resolve().parent.parent)
            with (work / "engine.log").open("wb") as log:
                process = subprocess.Popen(
                    [
                        sys.executable,
                        "-I",
                        "-c",
                        bootstrap,
                        package_root,
                        str(work / "config.json"),
                    ],
                    stdin=subprocess.PIPE if config["vision"] else None,
                    stdout=log,
                    stderr=log,
                    env=environment(work, options.get("tessdata_dir")),
                    **SUPERVISED,
                )
                group = contain(process)
                if config["vision"]:
                    # The key travels on a pipe so that no crash can leave it on disk.
                    def feed(stream, payload):
                        try:
                            stream.write(payload)
                            stream.close()
                        except OSError:
                            pass  # The worker ended first; its status is read below.

                    threading.Thread(
                        target=feed,
                        args=(process.stdin, json.dumps(vision_settings(options)).encode()),
                        daemon=True,
                    ).start()
                started = job_started
                peak_rss = 0
                peak_private_bytes = size
                progress_offset = 0
                next_disk_sample = 0.0

                def progress():
                    nonlocal progress_offset
                    path = work / "progress.jsonl"
                    if options["progress"] == "none" or not path.exists():
                        return
                    with path.open(encoding="utf-8") as stream:
                        stream.seek(progress_offset)
                        while True:
                            position = stream.tell()
                            line = stream.readline()
                            if not line:
                                break
                            if not line.endswith("\n"):
                                stream.seek(position)
                                break
                            event = json.loads(line)
                            if options["progress"] == "json":
                                print(json.dumps(event), file=sys.stderr, flush=True)
                            else:
                                print(
                                    f"vellric: {event['stage']} {event['done']}/{event['total']}",
                                    file=sys.stderr,
                                    flush=True,
                                )
                        progress_offset = stream.tell()

                while process.poll() is None:
                    if time.monotonic() - started > options["timeout_seconds"]:
                        raise JobError("deadline", "Job deadline exceeded", stage="supervision")
                    peak_rss = max(peak_rss, group_rss(group))
                    if time.monotonic() >= next_disk_sample:
                        staging_bytes, work_bytes = tree_size(staging), tree_size(work)
                        peak_private_bytes = max(peak_private_bytes, staging_bytes + work_bytes)
                        next_disk_sample = time.monotonic() + 1.0
                        if (
                            staging_bytes > options["max_output_bytes"]
                            or work_bytes > size + options["max_output_bytes"]
                        ):
                            raise JobError(
                                "resource-limit", "Job disk limit exceeded", stage="supervision"
                            )
                    if peak_rss > options["memory_mib"] * 1024 * 1024:
                        raise JobError(
                            "resource-limit",
                            "Job process-group memory exceeded",
                            stage="supervision",
                        )
                    progress()
                    time.sleep(0.1)
                progress()
            result_path = work / "result.json"
            if not result_path.is_file() or result_path.stat().st_size > 65536:
                raise JobError(
                    "internal-error",
                    "Worker exited without valid terminal status",
                    stage="supervision",
                    details={"worker_returncode": process.returncode},
                )
            try:
                result = json.loads(result_path.read_text(encoding="utf-8"))
                if not isinstance(result, dict) or set(result) != {"status", "exit_code"}:
                    raise ValueError
                status, code = result["status"], result["exit_code"]
                if (
                    not isinstance(status, dict)
                    or type(code) is not int
                    or code not in {0, 2, 3, 4, 5}
                ):
                    raise ValueError
                if process.returncode != code or status.get("schema") != STATUS_SCHEMA:
                    raise ValueError
                if not isinstance(status.get("stage"), str) or not status["stage"]:
                    raise ValueError
                if code == 0:
                    if (
                        status.get("status") != "complete"
                        or status.get("code") != "complete"
                        or type(status.get("page_count")) is not int
                        or status["page_count"] < 1
                    ):
                        raise ValueError
                else:
                    if (
                        status.get("status") not in {"failed", "blocked"}
                        or not isinstance(status.get("code"), str)
                        or status["code"] == "complete"
                        or not status["code"]
                        or not isinstance(status.get("message"), str)
                    ):
                        raise ValueError
                    page = status.get("page")
                    if page is not None and (type(page) is not int or page < 1):
                        raise ValueError
                    if not isinstance(status.get("details"), dict):
                        raise ValueError
                    failure = JobError(
                        status["code"],
                        status["message"],
                        stage=status["stage"],
                        page=page,
                        details=status["details"],
                    )
                    if failure.exit_code != code or failure.status()["status"] != status["status"]:
                        raise ValueError
            except (ValueError, TypeError, KeyError) as exc:
                raise JobError(
                    "internal-error", "Worker terminal protocol is invalid", stage="supervision"
                ) from exc
            if code:
                raise failure
            manifest = json.loads((staging / "manifest.json").read_text(encoding="utf-8"))
            if manifest.get("page_count") != status["page_count"]:
                raise JobError("artifact-invalid", "Worker page count differs from manifest")
            if manifest.get("source") != {"sha256": identity, "size": size}:
                raise JobError("artifact-invalid", "Artifact input identity mismatch")
            manifest["provenance"]["supervision"] = {
                "sampled_peak_group_rss_bytes": peak_rss,
                "sampled_peak_private_bytes": peak_private_bytes,
                "elapsed_seconds": time.monotonic() - job_started,
                "sampling_interval_seconds": 0.1,
                "disk_sampling_interval_seconds": 1.0,
                "measurement": "watchdog samples; transient peaks may be missed",
            }
            write_json(staging / "manifest.json", manifest)
            validate_bundle(staging, manifest)
            if tree_size(staging) > options["max_output_bytes"]:
                raise JobError("resource-limit", "Final output exceeds byte limit")
            publish(staging, target)
            return result["status"] | {
                "stage": "published",
                "source_sha256": identity,
                "output": str(target),
            }
        finally:
            if process is not None:
                if group is None:
                    process.kill()  # Stopped between starting the worker and holding its group.
                else:
                    kill_group(group)
                process.wait()
            if staging is not None and staging.exists():
                remove_tree(staging)


def main(argv: Sequence[str] | None = None) -> int:
    args = list(argv) if argv is not None else sys.argv[1:]
    want_json = "--status-json" in args
    if WINDOWS:
        # A redirected stream would otherwise take the legacy code page and refuse other text.
        for stream in (sys.stdout, sys.stderr):
            if hasattr(stream, "reconfigure"):
                stream.reconfigure(encoding="utf-8", errors="backslashreplace")
    try:
        p = parser()
        parsed = p.parse_args(args)
        if parsed.command is None:
            p.print_help()
            return 0
        if parsed.command == "doctor":
            data = doctor(language=parsed.language, tessdata_dir=parsed.tessdata_dir)
            if parsed.json:
                print(json.dumps(data, ensure_ascii=False, indent=2))
            else:
                print(f"vellric {__version__}: {data['enforcement']['publication']}")
                for name, entry in data["engines"].items():
                    print(f"{name}: {entry.get('version', 'unavailable')}")
            return 0
        options = vars(parsed)
        status = run_job(options)
        code = 0
    except JobError as exc:
        status, code = exc.status(), exc.exit_code
    except Exception:
        status, code = (
            JobError(
                "internal-error", "Filesystem or protocol failure; no success claimed"
            ).status(),
            5,
        )
    if want_json:
        print(json.dumps(status, ensure_ascii=False, allow_nan=False))
    else:
        print(
            f"vellric: {status['status']}: {status.get('message', status['code'])}", file=sys.stderr
        )
    return code


if __name__ == "__main__":
    raise SystemExit(main())
