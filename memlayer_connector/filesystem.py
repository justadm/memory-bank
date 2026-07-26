from __future__ import annotations

import errno
import os
import stat
from pathlib import Path
from uuid import uuid4


class RootBoundWriteError(OSError):
    pass


def root_identity(root: Path) -> tuple[int, int]:
    opened = os.open(
        root,
        os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0),
    )
    try:
        info = os.fstat(opened)
        return info.st_dev, info.st_ino
    finally:
        os.close(opened)


def write_atomic_beneath(
    *,
    root: Path,
    path: Path,
    data: bytes,
    mode: int | None = None,
    expected_root_identity: tuple[int, int] | None = None,
) -> None:
    try:
        relative = path.relative_to(root)
    except ValueError as exc:
        raise RootBoundWriteError("write path escapes project root") from exc
    if not relative.parts or any(part in {"", ".", ".."} for part in relative.parts):
        raise RootBoundWriteError("unsafe root-bound write path")

    nofollow = getattr(os, "O_NOFOLLOW", 0)
    directory_flags = os.O_RDONLY | os.O_DIRECTORY | nofollow
    root_fd = os.open(root, directory_flags)
    open_fds = [root_fd]
    try:
        info = os.fstat(root_fd)
        actual_root_identity = (info.st_dev, info.st_ino)
        if (
            expected_root_identity is not None
            and actual_root_identity != expected_root_identity
        ):
            raise RootBoundWriteError("project root identity changed")

        parent_fd = root_fd
        for component in relative.parts[:-1]:
            try:
                child_fd = os.open(component, directory_flags, dir_fd=parent_fd)
            except FileNotFoundError:
                os.mkdir(component, mode=0o755, dir_fd=parent_fd)
                child_fd = os.open(component, directory_flags, dir_fd=parent_fd)
            except OSError as exc:
                if exc.errno in {errno.ELOOP, errno.ENOTDIR}:
                    raise RootBoundWriteError(
                        f"symlink in root-bound write path: {relative.as_posix()}"
                    ) from exc
                raise
            open_fds.append(child_fd)
            parent_fd = child_fd

        target = relative.parts[-1]
        previous_mode: int | None = None
        try:
            target_info = os.stat(target, dir_fd=parent_fd, follow_symlinks=False)
        except FileNotFoundError:
            pass
        else:
            if stat.S_ISLNK(target_info.st_mode):
                raise RootBoundWriteError(
                    f"symlink in root-bound write path: {relative.as_posix()}"
                )
            if not stat.S_ISREG(target_info.st_mode):
                raise RootBoundWriteError(
                    f"root-bound write target is not a regular file: {relative.as_posix()}"
                )
            previous_mode = stat.S_IMODE(target_info.st_mode)

        temporary = f".{target}.{uuid4().hex}.tmp"
        temporary_created = False
        try:
            file_fd = os.open(
                temporary,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | nofollow,
                0o600,
                dir_fd=parent_fd,
            )
            temporary_created = True
            with os.fdopen(file_fd, "wb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            effective_mode = mode if mode is not None else previous_mode
            if effective_mode is not None:
                os.chmod(
                    temporary,
                    effective_mode,
                    dir_fd=parent_fd,
                    follow_symlinks=False,
                )
            os.replace(
                temporary,
                target,
                src_dir_fd=parent_fd,
                dst_dir_fd=parent_fd,
            )
            temporary_created = False
            os.fsync(parent_fd)
        finally:
            if temporary_created:
                try:
                    os.unlink(temporary, dir_fd=parent_fd)
                except FileNotFoundError:
                    pass
    finally:
        for descriptor in reversed(open_fds):
            os.close(descriptor)
