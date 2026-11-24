"""Verify a reaped Darwin process has no live descendants, including orphans."""

# cspell:words reparenting PIDUNIQIDENTIFIERINFO QQII libproc listallpids pidinfo

import ctypes
import os
import struct
import sys
import time
from typing import NamedTuple, cast

# XNU proc_info_private.h defines this stable 56-byte ABI. The original parent
# version survives reparenting and exec, when the parent unique ID can change.
_PROC_PIDUNIQIDENTIFIERINFO = 17
_IDENTITY = struct.Struct("=16xQQII16x")
_VERIFY_SECONDS = 1.0


class ProcessIdentity(NamedTuple):
    """Process creation identity and its kernel-recorded parent versions."""

    unique_id: int
    parent_id: int
    version: int
    original_parent_version: int


class DarwinProcessLineage:
    """Use XNU creation identities and process-list snapshots for teardown proof."""

    def __init__(self, libproc: ctypes.CDLL) -> None:
        self._list_pids = libproc.proc_listallpids
        self._list_pids.argtypes = [ctypes.c_void_p, ctypes.c_int]
        self._identity = libproc.proc_pidinfo
        self._identity.argtypes = [
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_uint64,
            ctypes.c_void_p,
            ctypes.c_int,
        ]

    @classmethod
    def open(cls) -> "DarwinProcessLineage | None":
        """Return no verifier when the native process inventory is unavailable."""
        if sys.platform != "darwin":
            return None
        try:
            return cls(ctypes.CDLL("/usr/lib/libproc.dylib"))
        except (AttributeError, OSError):
            return None

    def _read_identity(self, pid: int) -> ProcessIdentity | None:
        data = ctypes.create_string_buffer(_IDENTITY.size)
        size = self._identity(pid, _PROC_PIDUNIQIDENTIFIERINFO, 0, data, _IDENTITY.size)
        if size != _IDENTITY.size:
            return None
        identity = ProcessIdentity(*_IDENTITY.unpack(data))
        return identity if identity.unique_id > 0 else None

    def creation_id(self, pid: int) -> int | None:
        """Capture the launcher's identity while its unreaped PID is reserved."""
        try:
            identity = self._read_identity(pid)
        except OSError:
            return None
        return None if identity is None else identity.unique_id

    def _live_pids(self) -> list[int]:
        count = self._list_pids(None, 0)
        if count <= 0:
            return []
        data = (ctypes.c_int * (count + 64))()
        count = self._list_pids(data, ctypes.sizeof(data))
        pids = cast(list[int], data[:count]) if 0 < count <= len(data) else []
        # AI: XNU lists under the process-list lock, with kernel PID 0 at the
        # tail of the active list. A buffer that misses it may be truncated.
        if 0 not in pids:
            return []
        live = pids[: pids.index(0)]
        return live if 1 in live and os.getpid() in live else []

    def _stable_inventory(self) -> list[ProcessIdentity]:
        before = {pid: self._read_identity(pid) for pid in self._live_pids()}
        identities: list[ProcessIdentity] = []
        # AI: Match IDs on both sides of the atomic list. If a PID disappeared
        # or was reused, it cannot account for the process in that snapshot.
        for pid in self._live_pids():
            identity = before.get(pid)
            if identity is None or self._read_identity(pid) != identity:
                return []
            identities.append(identity)
        return identities

    def verify_after_reap(self, launcher_id: int) -> bool:
        """Require an inventory in which every live process is provably unrelated."""
        deadline = time.monotonic() + _VERIFY_SECONDS
        while True:
            try:
                identities = self._stable_inventory()
            except OSError:
                return False
            if identities and _exclude_descendants(identities, launcher_id):
                return True
            if time.monotonic() >= deadline:
                return False
            time.sleep(0.05)


def _exclude_descendants(identities: list[ProcessIdentity], launcher_id: int) -> bool:
    unrelated: dict[int, int] = {}
    for identity in sorted(identities):
        if identity.unique_id >= launcher_id:
            # AI: A process created during the run needs a verified chain to
            # a process older than the launcher. Missing ancestors and an exec
            # after reparenting cannot turn an orphan into an unrelated process.
            parent_version = unrelated.get(identity.parent_id)
            if identity.unique_id == launcher_id or (
                parent_version is None
                or parent_version != identity.original_parent_version
            ):
                return False
        unrelated[identity.unique_id] = identity.version
    return True
