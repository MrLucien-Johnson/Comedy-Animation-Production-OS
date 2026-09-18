"""Generation concurrency lock — LOW_6GB defaults to serial jobs only."""

from __future__ import annotations

import os
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from capos.core.paths import project_root
from capos.hardware.profile import (
    assert_single_concurrency,
    load_hardware_profile,
    resolve_generation_settings,
)


def lock_path(*, root: Path | None = None) -> Path:
    base = (root or project_root()) / "logs" / "locks"
    base.mkdir(parents=True, exist_ok=True)
    return base / "generation.lock"


@contextmanager
def generation_slot(*, root: Path | None = None, wait_s: float = 600.0) -> Iterator[None]:
    """Acquire exclusive generation slot. Concurrency must be 1 on LOW_6GB."""
    profile = load_hardware_profile(root=root)
    assert_single_concurrency(profile)
    settings = resolve_generation_settings(profile)
    if settings["concurrency"] != 1:
        # Still serialise via lock even if misconfigured
        pass
    path = lock_path(root=root)
    deadline = time.time() + wait_s
    fd: int | None = None
    while time.time() < deadline:
        try:
            fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, f"pid={os.getpid()} t={time.time()}\n".encode())
            break
        except FileExistsError:
            # Stale lock recovery: if older than wait_s, remove
            try:
                age = time.time() - path.stat().st_mtime
                if age > wait_s:
                    path.unlink(missing_ok=True)
                    continue
            except OSError:
                pass
            time.sleep(0.25)
    else:
        raise TimeoutError("Could not acquire generation lock (concurrency=1)")
    try:
        yield
    finally:
        if fd is not None:
            try:
                os.close(fd)
            except OSError:
                pass
        path.unlink(missing_ok=True)
