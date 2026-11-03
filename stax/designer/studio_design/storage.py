"""Atomic file writes (Slice R1, REVIEW-GBT2 §B item 5 / §A.5).

Every byte this package persists — document directories, snapshot
bundles, library files, exports a host asks it to write — lands
through ONE sink: write to a temp file IN THE SAME DIRECTORY,
fsync, then `os.replace` onto the final path. A crash or kill at
any point leaves the final path holding either the complete old
bytes or the complete new bytes, never a torn file, and the temp
file is removed on failure. `os.replace` is atomic on the same
filesystem on both POSIX and Windows, and the temp file is created
in the target's own directory precisely so the replace never
crosses filesystems.

This module is the ONLY place in studio_design/ that opens a file
for writing; everything else builds bytes in memory and hands
them here (or to a host, which owns its own sinks).
"""

from __future__ import annotations

import os
import tempfile


def atomic_write_bytes(path: str, data: bytes) -> str:
    """Write `data` to `path` atomically (temp + fsync + rename).

    The parent directory is created if needed. On any failure the
    temp file is removed and the previous content at `path` (if
    any) is untouched. Returns the path written."""
    directory = os.path.dirname(os.path.abspath(path))
    os.makedirs(directory, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=directory, prefix=".tmp-", suffix=".part")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    return path


def atomic_write_text(path: str, text: str, encoding: str = "utf-8") -> str:
    """atomic_write_bytes for text payloads (JSON records, indexes)."""
    return atomic_write_bytes(path, text.encode(encoding))
