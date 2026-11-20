"""Local command transport for the Bedrock Converse wire protocol."""

from __future__ import annotations

import json
import os
import selectors
import subprocess
import sys
import time
from collections.abc import Iterator
from pathlib import Path

from .runtime import WINDOWS, JobError, kill_group, require_open_fds

REQUEST_SCHEMA = "bedrock-converse-request/1"
RESPONSE_SCHEMA = "bedrock-converse-response/1"
RESPONSE_LIMIT = 16 * 1024 * 1024
CATEGORIES = {"throttled", "refused", "unavailable", "invalid", "limit"}
STOP_REASONS = {
    "end_turn",
    "tool_use",
    "max_tokens",
    "stop_sequence",
    "guardrail_intervened",
    "content_filtered",
    "malformed_model_output",
    "malformed_tool_use",
    "model_context_window_exceeded",
}

# Publish the group before the configured program can run. A supervisor that has
# reaped the worker can clean up every published group. A late bootstrap whose
# worker died exits without executing the configured program.
BOOTSTRAP = """
import os, sys
worker = int(sys.argv[1])
marker = os.path.join(sys.argv[2], '.broker-' + str(os.getpid()))
os.close(os.open(marker, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600))
if os.getppid() != worker:
    sys.exit(1)
names = sys.argv[3].split(',') if sys.argv[3] else []
os.execve(sys.argv[4], sys.argv[4:], {name: os.environ[name] for name in names})
"""


def in_session(pid: int, group: int, session: int) -> bool:
    try:
        return os.getpgid(pid) == group and os.getsid(pid) == session
    except ProcessLookupError:
        return False


def group_alive(group: int, session: int) -> bool:
    if in_session(group, group, session):
        return True
    # A broker can exit while its descendants still hold the group's pipes.
    if sys.platform == "darwin":
        from . import _darwin

        members = _darwin._members(group)
    else:
        members = (int(entry.name) for entry in Path("/proc").iterdir() if entry.name.isdecimal())
    return any(in_session(pid, group, session) for pid in members)


def active_groups(work: Path, session: int) -> Iterator[int]:
    for marker in work.glob(".broker-*"):
        pid = marker.name.removeprefix(".broker-")
        if pid.isascii() and pid.isdecimal() and 1 < int(pid) <= 2**31 - 1:
            group = int(pid)
            if group != session and group_alive(group, session):
                yield group


def reap_groups(work: Path, session: int) -> None:
    try:
        for group in active_groups(work, session):
            kill_group(group)
    except OSError as exc:
        raise JobError(
            "dependency-unavailable", "Cannot observe broker process groups", stage="supervision"
        ) from exc


def failure(category: str, page: int | None) -> JobError:
    code = "vision-refused" if category == "refused" else "vision-operational"
    return JobError(
        code,
        "Bedrock broker request failed",
        stage="vision",
        page=page,
        details={"category": category},
    )


def unique_object(pairs: list) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError
        result[key] = value
    return result


def invalid_constant(_value: str) -> None:
    raise ValueError


def decode(raw: bytes, page: int | None) -> dict:
    try:
        envelope = json.loads(
            raw.decode("utf-8"), object_pairs_hook=unique_object, parse_constant=invalid_constant
        )
        if not isinstance(envelope, dict) or envelope.get("schema") != RESPONSE_SCHEMA:
            raise ValueError
        if envelope.get("status") == "error":
            category = envelope.get("category")
            if set(envelope) != {"schema", "status", "category"} or category not in CATEGORIES:
                raise ValueError
            raise failure(category, page)
        if envelope.get("status") != "ok" or set(envelope) != {"schema", "status", "body"}:
            raise ValueError
        body = envelope["body"]
        if (
            not isinstance(body, dict)
            or body.keys()
            - {
                "stopReason",
                "output",
                "usage",
                "metrics",
                "additionalModelResponseFields",
                "trace",
                "performanceConfig",
                "serviceTier",
            }
            or body["stopReason"] not in STOP_REASONS
            or not isinstance(body["output"], dict)
            or set(body["output"]) != {"message"}
        ):
            raise ValueError
        message = body["output"]["message"]
        if (
            not isinstance(message, dict)
            or set(message) != {"role", "content"}
            or message["role"] != "assistant"
        ):
            raise ValueError
        content = message["content"]
        if not isinstance(content, list) or not all(
            isinstance(block, dict)
            and (
                (set(block) == {"text"} and isinstance(block["text"], str))
                or (
                    set(block) == {"reasoningContent"}
                    and isinstance(block["reasoningContent"], dict)
                )
            )
            for block in content
        ):
            raise ValueError
        if body["stopReason"] == "end_turn" and not any("text" in block for block in content):
            raise ValueError
        for block in content:
            if "text" in block:
                block["text"].encode("utf-8", errors="strict")
        usage = body.get("usage", {})
        if not isinstance(usage, dict) or any(
            key in usage and (type(usage[key]) is not int or usage[key] < 0)
            for key in ("inputTokens", "outputTokens", "totalTokens")
        ):
            raise ValueError
    except (LookupError, TypeError, ValueError, RecursionError) as exc:
        raise failure("invalid", page) from exc
    return body


def exchange(process, payload: bytes, deadline: float, page, cancel_event) -> bytes:
    response = bytearray()
    remaining = memoryview(payload)
    with selectors.DefaultSelector() as selector:
        for stream, event in (
            (process.stdin, selectors.EVENT_WRITE),
            (process.stdout, selectors.EVENT_READ),
        ):
            os.set_blocking(stream.fileno(), False)
            selector.register(stream, event)
        while selector.get_map() or process.poll() is None:
            if cancel_event is not None and cancel_event.is_set():
                raise JobError("deadline", "Vision pass cancelled", stage="vision", page=page)
            left = deadline - time.monotonic()
            if left <= 0:
                raise failure("unavailable", page)
            for key, event in selector.select(min(left, 0.05)):
                try:
                    if event == selectors.EVENT_WRITE:
                        remaining = remaining[os.write(key.fd, remaining) :]
                        done = not remaining
                    else:
                        chunk = os.read(key.fd, min(65536, RESPONSE_LIMIT + 1 - len(response)))
                        response.extend(chunk)
                        if len(response) > RESPONSE_LIMIT:
                            raise failure("limit", page)
                        done = not chunk
                except BlockingIOError:
                    continue
                if done:
                    selector.unregister(key.fileobj)
                    key.fileobj.close()
    if process.returncode:
        raise failure("unavailable", page)
    if remaining:
        raise failure("invalid", page)
    return bytes(response)


def converse(settings: dict, body: dict, page, timeout: float, work: Path, cancel_event) -> dict:
    command = settings["command"]
    fds = tuple(command["pass_fds"])
    require_open_fds(fds, stage="vision")
    payload = json.dumps(
        {
            "schema": REQUEST_SCHEMA,
            "region": settings["region"],
            "model": settings["model"],
            "body": body,
        },
        allow_nan=False,
    ).encode("utf-8")
    deadline = time.monotonic() + timeout
    try:
        process = subprocess.Popen(
            [
                sys.executable,
                "-I",
                "-S",
                "-c",
                BOOTSTRAP,
                str(os.getpid()),
                str(work),
                ",".join(settings["env"]),
                *command["argv"],
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            cwd=work,
            env=settings["env"],
            close_fds=True,
            pass_fds=fds,
            process_group=0,
        )
    except OSError as exc:
        raise failure("unavailable", page) from exc
    try:
        return decode(exchange(process, payload, deadline, page, cancel_event), page)
    except OSError as exc:
        raise failure("unavailable", page) from exc
    finally:
        marker = work / f".broker-{process.pid}"
        try:
            if WINDOWS:
                # Windows has no POSIX sessions or process groups, and the command
                # transport is refused there before any broker starts; the broker
                # leader is the only process this call owns.
                if process.poll() is None:
                    process.kill()
            elif process.poll() is None or group_alive(process.pid, os.getsid(0)):
                kill_group(process.pid)
        except OSError as exc:
            # Keep the marker so the supervisor can retry observing any descendants.
            process.kill()
            raise JobError(
                "dependency-unavailable",
                "Cannot observe broker process groups",
                stage="vision",
                page=page,
            ) from exc
        else:
            marker.unlink(missing_ok=True)
        finally:
            process.wait()
            process.stdin.close()
            process.stdout.close()
