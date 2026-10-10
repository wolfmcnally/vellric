"""Windows job objects: a process and everything it starts are measured and ended together."""

from __future__ import annotations

import ctypes
import time
from ctypes import wintypes

kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

BASIC_PROCESS_ID_LIST = 3
EXTENDED_LIMIT_INFORMATION = 9
KILL_ON_JOB_CLOSE = 0x2000
PROCESS_TERMINATE = 0x0001
PROCESS_SET_QUOTA = 0x0100
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
ERROR_MORE_DATA = 234
LISTED = 4096


class BasicLimits(ctypes.Structure):
    _fields_ = [
        ("PerProcessUserTimeLimit", ctypes.c_longlong),
        ("PerJobUserTimeLimit", ctypes.c_longlong),
        ("LimitFlags", wintypes.DWORD),
        ("MinimumWorkingSetSize", ctypes.c_size_t),
        ("MaximumWorkingSetSize", ctypes.c_size_t),
        ("ActiveProcessLimit", wintypes.DWORD),
        ("Affinity", ctypes.c_size_t),
        ("PriorityClass", wintypes.DWORD),
        ("SchedulingClass", wintypes.DWORD),
    ]


class ExtendedLimits(ctypes.Structure):
    _fields_ = [
        ("BasicLimitInformation", BasicLimits),
        ("IoInfo", ctypes.c_ulonglong * 6),
        ("ProcessMemoryLimit", ctypes.c_size_t),
        ("JobMemoryLimit", ctypes.c_size_t),
        ("PeakProcessMemoryUsed", ctypes.c_size_t),
        ("PeakJobMemoryUsed", ctypes.c_size_t),
    ]


class ProcessIds(ctypes.Structure):
    _fields_ = [
        ("NumberOfAssignedProcesses", wintypes.DWORD),
        ("NumberOfProcessIdsInList", wintypes.DWORD),
        ("ProcessIdList", ctypes.c_size_t * LISTED),
    ]


class MemoryCounters(ctypes.Structure):
    _fields_ = [
        ("cb", wintypes.DWORD),
        ("PageFaultCount", wintypes.DWORD),
        ("PeakWorkingSetSize", ctypes.c_size_t),
        ("WorkingSetSize", ctypes.c_size_t),
        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
        ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
        ("PagefileUsage", ctypes.c_size_t),
        ("PeakPagefileUsage", ctypes.c_size_t),
    ]


def _declare(name, result, *arguments):
    function = getattr(kernel32, name)
    function.restype, function.argtypes = result, arguments
    return function


_create = _declare("CreateJobObjectW", wintypes.HANDLE, wintypes.LPVOID, wintypes.LPCWSTR)
_set = _declare(
    "SetInformationJobObject",
    wintypes.BOOL,
    wintypes.HANDLE,
    ctypes.c_int,
    wintypes.LPVOID,
    wintypes.DWORD,
)
_query = _declare(
    "QueryInformationJobObject",
    wintypes.BOOL,
    wintypes.HANDLE,
    ctypes.c_int,
    wintypes.LPVOID,
    wintypes.DWORD,
    wintypes.LPDWORD,
)
_assign = _declare("AssignProcessToJobObject", wintypes.BOOL, wintypes.HANDLE, wintypes.HANDLE)
_terminate = _declare("TerminateJobObject", wintypes.BOOL, wintypes.HANDLE, wintypes.UINT)
_open = _declare("OpenProcess", wintypes.HANDLE, wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
_close = _declare("CloseHandle", wintypes.BOOL, wintypes.HANDLE)
_memory = _declare(
    "K32GetProcessMemoryInfo",
    wintypes.BOOL,
    wintypes.HANDLE,
    ctypes.POINTER(MemoryCounters),
    wintypes.DWORD,
)


def contain(pid: int) -> int | None:
    """A job that holds ``pid`` and its future children; None when it could not be formed.

    The job ends its members when its last handle closes, so they cannot outlive this process.
    """
    job = _create(None, None)
    if not job:
        return None
    limits = ExtendedLimits()
    limits.BasicLimitInformation.LimitFlags = KILL_ON_JOB_CLOSE
    process = _open(PROCESS_SET_QUOTA | PROCESS_TERMINATE, False, pid)
    try:
        if (
            process
            and _set(job, EXTENDED_LIMIT_INFORMATION, ctypes.byref(limits), ctypes.sizeof(limits))
            and _assign(job, process)
        ):
            return job
    finally:
        if process:
            _close(process)
    _close(job)
    return None


def _members(job: int) -> list[int]:
    listing = ProcessIds()
    done = _query(job, BASIC_PROCESS_ID_LIST, ctypes.byref(listing), ctypes.sizeof(listing), None)
    if not done and ctypes.get_last_error() != ERROR_MORE_DATA:
        raise OSError(ctypes.get_last_error(), "Job membership query failed")
    return list(listing.ProcessIdList[: listing.NumberOfProcessIdsInList])


def end(job: int, *, wait: float = 5.0) -> None:
    """End every member, wait for them to go so their files are released, and drop the job."""
    try:
        _terminate(job, 1)
        deadline = time.monotonic() + wait
        while _members(job) and time.monotonic() < deadline:
            time.sleep(0.01)
    finally:
        _close(job)


def working_set(job: int) -> int:
    """Resident bytes summed over the job's members; a member that just ended counts nothing."""
    total = 0
    for pid in _members(job):
        process = _open(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not process:
            continue
        try:
            counters = MemoryCounters()
            counters.cb = ctypes.sizeof(counters)
            if _memory(process, ctypes.byref(counters), counters.cb):
                total += counters.WorkingSetSize
        finally:
            _close(process)
    return total
