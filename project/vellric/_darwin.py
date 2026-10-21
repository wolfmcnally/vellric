"""Native macOS resident-byte observations of a supervised process group."""

from __future__ import annotations

import ctypes
import errno
import functools
import os
import subprocess
import sys


class TaskInfo(ctypes.Structure):
    """Darwin sys/proc_info.h proc_taskinfo: six uint64, twelve int32 fields."""

    _fields_ = [
        (name, ctypes.c_uint64)
        for name in (
            "virtual_size",
            "resident_size",
            "total_user",
            "total_system",
            "threads_user",
            "threads_system",
        )
    ] + [
        (name, ctypes.c_int32)
        for name in (
            "policy",
            "faults",
            "pageins",
            "cow_faults",
            "messages_sent",
            "messages_received",
            "syscalls_mach",
            "syscalls_unix",
            "csw",
            "threadnum",
            "numrunning",
            "priority",
        )
    ]


@functools.lru_cache(maxsize=1)
def _library():
    library = ctypes.CDLL("/usr/lib/libproc.dylib", use_errno=True)
    try:
        library.proc_listpgrppids.argtypes = [ctypes.c_int, ctypes.c_void_p, ctypes.c_int]
        library.proc_listpgrppids.restype = ctypes.c_int
        library.proc_pidinfo.argtypes = [
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_uint64,
            ctypes.c_void_p,
            ctypes.c_int,
        ]
        library.proc_pidinfo.restype = ctypes.c_int
    except AttributeError as error:
        raise OSError(errno.ENOSYS, "Native process observation symbols are unavailable") from error
    return library


def _members(group: int) -> list[int]:
    # The wrapper returns PID count, not bytes. A full buffer may be truncated.
    capacity = 64
    for _ in range(8):
        buffer = (ctypes.c_int * capacity)()
        ctypes.set_errno(0)
        count = _library().proc_listpgrppids(group, buffer, ctypes.sizeof(buffer))
        error = ctypes.get_errno()
        if count <= 0 and error == errno.ESRCH:
            return []  # Caller confirms the group really disappeared.
        if count < 0 or (count == 0 and error):
            raise OSError(error or errno.EIO, "Native process-group enumeration failed")
        if count < capacity:
            members = list(buffer[:count])
            if any(pid <= 0 for pid in members) or len(set(members)) != len(members):
                raise OSError(errno.EIO, "Invalid native process-group enumeration")
            return members
        capacity *= 2
    raise OSError(errno.EOVERFLOW, "Native process-group enumeration stayed truncated")


def _task_rss(pid: int) -> int | None:
    info = TaskInfo()
    ctypes.set_errno(0)
    size = _library().proc_pidinfo(pid, 4, 0, ctypes.byref(info), ctypes.sizeof(info))
    error = ctypes.get_errno()
    if size == 0 and error == errno.ESRCH:
        return None  # The member exited between enumeration and observation.
    if size != ctypes.sizeof(info):
        raise OSError(error or errno.EIO, "Native resident-byte observation failed or was short")
    return info.resident_size


def group_rss(group: int) -> int:
    if group <= 0:
        raise OSError(errno.EINVAL, "A positive supervised process-group ID is required")
    members = _members(group)
    if not members:
        try:
            os.killpg(group, 0)
        except ProcessLookupError:
            return 0  # An actually exited group has no resident memory.
        raise OSError(errno.EIO, "A live process group could not be observed")
    total = 0
    for pid in members:
        try:
            if os.getpgid(pid) != group:
                continue
        except ProcessLookupError:
            continue
        resident = _task_rss(pid)
        if resident is None:
            continue
        try:
            if os.getpgid(pid) == group:
                total += resident
        except ProcessLookupError:
            continue
    return total


def available() -> bool:
    """Probe the complete observer on a fresh owned group, never the caller's group."""
    try:
        with subprocess.Popen(
            [sys.executable, "-I", "-c", "import sys; sys.stdin.buffer.read()"],
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env={},
            cwd="/",
            start_new_session=True,
        ) as process:
            try:
                usable = group_rss(process.pid) > 0 and process.poll() is None
            finally:
                process.stdin.close()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
                    usable = False
            return usable
    except OSError:
        return False
