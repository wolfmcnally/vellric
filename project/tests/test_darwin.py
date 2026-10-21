"""Native observer boundary oracles; fake kernel replies need no Darwin host."""

import ctypes
import errno
import io

import pytest

from vellric import _darwin, cli, runtime


def test_native_group_observation_refuses_unknown_memory(monkeypatch):
    group = 700001
    case = "normal"
    list_calls = 0
    native_library = _darwin._library.__wrapped__

    class Kernel:
        def proc_listpgrppids(self, requested, buffer, size):
            nonlocal list_calls
            assert requested == group
            list_calls += 1
            capacity = size // ctypes.sizeof(ctypes.c_int)
            if case == "denied-list":
                ctypes.set_errno(errno.EPERM)
                return 0
            if case == "truncated" or (case == "grow" and list_calls == 1):
                return capacity
            if case.startswith("empty"):
                if case == "empty-esrch":
                    ctypes.set_errno(errno.ESRCH)
                return 0
            buffer[0], buffer[1] = group, group + 1
            if case == "invalid":
                buffer[1] = group
            return 2

        def proc_pidinfo(self, pid, flavor, argument, buffer, size):
            assert flavor == 4 and argument == 0 and size == 96
            if case == "denied-task":
                ctypes.set_errno(errno.EPERM)
                return 0
            if case == "zero-task":
                return 0
            if case == "short-task":
                return 48
            if case == "short-esrch":
                ctypes.set_errno(errno.ESRCH)
                return 48
            if case == "exited-member" and pid == group + 1:
                ctypes.set_errno(errno.ESRCH)
                return 0
            info = ctypes.cast(buffer, ctypes.POINTER(_darwin.TaskInfo)).contents
            info.virtual_size = 1000000  # Virtual bytes must not become the RSS oracle.
            info.resident_size = 8192 if pid == group else 16384
            return 96

    def membership(pid):
        if case == "departed-member" and pid == group + 1:
            return group + 10
        if case == "vanished-member" and pid == group + 1:
            raise ProcessLookupError(errno.ESRCH, "Exited")
        return group

    def group_exists(pid, sig):
        assert pid == group and sig == 0
        if case in {"empty-exited", "empty-esrch"}:
            raise ProcessLookupError(errno.ESRCH, "Exited")
        if case == "empty-denied":
            raise PermissionError(errno.EPERM, "Denied")

    monkeypatch.setattr(_darwin, "_library", lambda: Kernel())
    monkeypatch.setattr(_darwin.os, "getpgid", membership, raising=False)
    monkeypatch.setattr(_darwin.os, "killpg", group_exists, raising=False)
    monkeypatch.setattr(runtime, "WINDOWS", False)
    monkeypatch.setattr(runtime.sys, "platform", "darwin")
    assert ctypes.sizeof(_darwin.TaskInfo) == 96
    assert _darwin.TaskInfo.resident_size.offset == 8
    for case, expected in [
        ("normal", 24576),
        ("grow", 24576),
        ("exited-member", 8192),
        ("departed-member", 8192),
        ("vanished-member", 8192),
        ("empty-exited", 0),
        ("empty-esrch", 0),
    ]:
        list_calls = 0
        assert runtime.group_rss(group) == expected, case
        if case == "grow":
            assert list_calls == 2
    for case in [
        "denied-list",
        "denied-task",
        "zero-task",
        "short-task",
        "short-esrch",
        "truncated",
        "invalid",
        "empty-live",
        "empty-denied",
    ]:
        list_calls = 0
        with pytest.raises(runtime.JobError) as error:
            runtime.group_rss(group)
        assert error.value.code == "dependency-unavailable", case
        assert error.value.stage == "supervision", case
        assert isinstance(error.value.__cause__, OSError), case
        if case == "truncated":
            assert list_calls == 8  # Bounded growth; never quietly accept a full buffer.

    with monkeypatch.context() as missing:
        missing.setattr(_darwin, "_library", native_library)
        missing.setattr(ctypes, "CDLL", lambda *args, **kwargs: object())
        with pytest.raises(runtime.JobError) as error:
            runtime.group_rss(group)
        assert error.value.code == "dependency-unavailable"
        assert error.value.__cause__.errno == errno.ENOSYS


def test_doctor_native_probe_reaps_its_group_and_reports_denial(monkeypatch):
    attempts = []
    denied = False
    resident = 8192

    class Probe:
        pid = 700001

        def __init__(self, command, **kwargs):
            assert command[1:3] == ["-I", "-c"]
            assert kwargs["start_new_session"] and kwargs["env"] == {}
            self.stdin = io.BytesIO()
            self.returncode = None
            attempts.append(self)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            assert self.stdin.closed and self.returncode == 0

        def poll(self):
            return self.returncode

        def wait(self, timeout):
            assert self.stdin.closed and timeout == 5
            self.returncode = 0

    def observe(group):
        assert group == Probe.pid
        if denied:
            raise PermissionError(errno.EPERM, "Denied native observation")
        return resident

    monkeypatch.setattr(_darwin.subprocess, "Popen", Probe)
    monkeypatch.setattr(_darwin, "group_rss", observe)
    monkeypatch.setattr(runtime, "WINDOWS", False)
    monkeypatch.setattr(cli, "WINDOWS", False)
    monkeypatch.setattr(runtime.sys, "platform", "darwin")
    monkeypatch.setattr(cli, "find_program", lambda *args, **kwargs: None)
    monkeypatch.setattr(cli, "publication_available", lambda: True)
    assert cli.doctor()["enforcement"]["rss_available"] is True
    resident = 0
    assert cli.doctor()["enforcement"]["rss_available"] is False
    denied = True
    assert cli.doctor()["enforcement"]["rss_available"] is False
    assert len(attempts) == 3
