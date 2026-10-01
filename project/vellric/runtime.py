"""Bounded subprocesses, private environments and exclusive artifact publication."""

from __future__ import annotations

import ctypes
import errno
import hashlib
import json
import os
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

SCHEMA = "vellric.document/1.0"
STATUS_SCHEMA = "vellric.status/1.0"
PYMUPDF_VERSION = "1.28.2"
BEHAVIOR = f"drawbridge-0.4.3-pymupdf-{PYMUPDF_VERSION}/v1"


class JobError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        stage: str = "job",
        page: int | None = None,
        details: dict | None = None,
    ):
        super().__init__(message)
        self.code, self.stage, self.page, self.details = code, stage, page, details or {}

    def status(self) -> dict:
        blocked = self.code in {"password-protected", "degenerate-input"}
        return {
            "schema": STATUS_SCHEMA,
            "status": "blocked" if blocked else "failed",
            "code": self.code,
            "stage": self.stage,
            "page": self.page,
            "message": str(self),
            "details": self.details,
            "retry_hint": {
                "retry_unchanged": False,
                "reason": "Change input, credentials, settings or environment before retrying.",
            },
        }

    @property
    def exit_code(self) -> int:
        if self.code == "usage":
            return 2
        if self.code in {"password-protected", "degenerate-input"}:
            return 3
        if self.code in {
            "not-pdf",
            "malformed-pdf",
            "pdf-open-operational",
            "pdf-read-operational",
            "source-hash-mismatch",
        }:
            return 4
        return 5


def environment(temp: Path, tessdata_dir: str | None = None) -> dict[str, str]:
    """No inherited credentials, Python/loader injection or user tool plugins."""
    values = {
        "PATH": str(Path(sys.prefix) / "bin") + ":/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin",
        "HOME": str(temp),
        "TMPDIR": str(temp),
        "LANG": "en_US.UTF-8",
        "LC_ALL": "en_US.UTF-8",
        "OMP_THREAD_LIMIT": "1",
        "PYTHONNOUSERSITE": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    if tessdata_dir is not None:
        values["TESSDATA_PREFIX"] = tessdata_dir
    return values


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def write_json(path: Path, data: dict) -> None:
    path.write_text(
        json.dumps(data, ensure_ascii=False, allow_nan=False, indent=2) + "\n", encoding="utf-8"
    )


def tree_size(path: Path) -> int:
    return sum(p.stat().st_size for p in path.rglob("*") if p.is_file())


def run_tool(
    command: list[str],
    *,
    timeout: float,
    temp: Path,
    code: str = "ocr-operational",
    limit: int = 64 * 1024 * 1024,
    stage: str = "recognition",
    tessdata_dir: str | None = None,
    cancel_event=None,
) -> str:
    """Files avoid unbounded capture; the supervisor owns the inherited process group."""
    with tempfile.TemporaryFile(dir=temp) as out, tempfile.TemporaryFile(dir=temp) as err:
        try:
            process = subprocess.Popen(
                command, stdout=out, stderr=err, env=environment(temp, tessdata_dir)
            )
        except OSError as exc:
            raise JobError(
                "dependency-unavailable", "Required executable cannot start", stage=stage
            ) from exc
        started = time.monotonic()
        try:
            while process.poll() is None:
                if cancel_event is not None and cancel_event.is_set():
                    raise JobError(
                        "deadline", "Recognition cancelled after page failure", stage=stage
                    )
                if time.monotonic() - started > timeout:
                    raise JobError("deadline", "External engine deadline exceeded", stage=stage)
                if os.fstat(out.fileno()).st_size + os.fstat(err.fileno()).st_size > limit:
                    raise JobError(
                        "resource-limit", "External engine output exceeds limit", stage=stage
                    )
                time.sleep(0.05)
            if process.returncode:
                raise JobError(
                    code,
                    "External engine refused the job",
                    stage=stage,
                    details={"backend_returncode": process.returncode},
                )
            if os.fstat(out.fileno()).st_size > limit:
                raise JobError(
                    "resource-limit", "External engine output exceeds limit", stage=stage
                )
            out.seek(0)
            return out.read(limit + 1).decode("utf-8", errors="strict")
        finally:
            if process.poll() is None:
                process.kill()
            process.wait()


def publish(staging: Path, target: Path) -> None:
    """Atomic no-replace rename on qualified macOS and Linux; no racy fallback."""
    libc = ctypes.CDLL(None, use_errno=True)
    source, dest = os.fsencode(staging), os.fsencode(target)
    if sys.platform == "darwin":
        fn = libc.renameatx_np
        fn.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
        result = fn(-2, source, -2, dest, 4)  # AT_FDCWD; RENAME_EXCL
    elif sys.platform.startswith("linux") and hasattr(libc, "renameat2"):
        fn = libc.renameat2
        fn.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
        result = fn(-100, source, -100, dest, 1)  # RENAME_NOREPLACE
    else:
        raise JobError("artifact-invalid", "Exclusive publication is unavailable on this platform")
    if result:
        error = ctypes.get_errno()
        raise JobError(
            "artifact-invalid",
            "Destination exists or exclusive publication failed",
            stage="publication",
            details={"errno": errno.errorcode.get(error, str(error))},
        )


def validate_bundle(root: Path, manifest: dict) -> None:
    """Consumer-side validation is also available without importing a PDF engine."""
    if manifest.get("schema") != SCHEMA or manifest.get("status") != "complete":
        raise JobError("artifact-invalid", "Invalid complete manifest")
    count = manifest.get("page_count")
    pages = manifest.get("pages", [])
    if (
        type(count) is not int
        or count < 1
        or [p.get("number") for p in pages] != list(range(1, count + 1))
    ):
        raise JobError("artifact-invalid", "Manifest page count/order mismatch")
    seen = set()
    for entry in manifest.get("files", []):
        rel = entry["path"]
        path = Path(rel)
        if path.is_absolute() or ".." in path.parts or rel in seen:
            raise JobError("artifact-invalid", "Unsafe or duplicate artifact path")
        seen.add(rel)
        full = root / path
        current = root
        if current.is_symlink():
            raise JobError("artifact-invalid", "Artifact symlink refused")
        for component in path.parts:
            current = current / component
            if current.is_symlink():
                raise JobError("artifact-invalid", "Artifact symlink refused")
        if (
            not full.is_file()
            or full.stat().st_size != entry["size"]
            or digest(full) != entry["sha256"]
        ):
            raise JobError("artifact-invalid", "Artifact size or digest mismatch")
    actual = {
        str(p.relative_to(root))
        for p in root.rglob("*")
        if p.is_file() and p.name != "manifest.json"
    }
    if actual != seen:
        raise JobError("artifact-invalid", "Artifact inventory mismatch")
    for page in pages:
        for key in ("native", "text"):
            if page["files"].get(key) not in seen:
                raise JobError("artifact-invalid", "Required page artifact missing")
    if manifest["job"] in ("inspect", "convert") and not {"document.txt", "document.md"} <= seen:
        raise JobError("artifact-invalid", "Required document artifact missing")


def kill_group(pid: int) -> None:
    try:
        os.killpg(pid, signal.SIGKILL)
    except ProcessLookupError:
        pass


def group_rss(pid: int) -> int:
    """Watchdog measurement of the job group; not a hard memory sandbox."""
    if sys.platform.startswith("linux"):
        proc = Path("/proc")
        if not proc.is_dir():
            raise JobError("dependency-unavailable", "Linux procfs is required for RSS supervision")
        total = 0
        for entry in proc.iterdir():
            if not entry.name.isdecimal():
                continue
            try:
                fields = (entry / "stat").read_text().rsplit(")", 1)[1].split()
                if int(fields[2]) == pid:
                    total += max(0, int(fields[21])) * os.sysconf("SC_PAGE_SIZE")
            except (FileNotFoundError, ProcessLookupError):
                continue  # A process disappeared between enumeration and measurement.
        return total
    if not Path("/bin/ps").is_file():
        raise JobError("dependency-unavailable", "/bin/ps is required for RSS supervision")
    result = subprocess.run(
        ["/bin/ps", "-axo", "pgid=,rss="], capture_output=True, text=True, check=True
    )
    return sum(
        int(row.split()[1]) * 1024
        for row in result.stdout.splitlines()
        if len(row.split()) == 2 and row.split()[0] == str(pid)
    )
