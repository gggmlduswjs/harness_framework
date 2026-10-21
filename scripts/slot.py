#!/usr/bin/env python3
"""제품×레이어 worktree 슬롯을 잡고 놓는다. worktree 정리는 사람이 한다.

제품·레이어·상한·슬롯 폴더는 harness.json 「slots」·「worktree_base」.
.slot-lock 이름·JSON 형식({issue, phase, pid, started_at})은 바꾸지 않는다 — gitwatch 가 읽는다.
원본: bigsix scripts/slot.py
"""

import argparse
import contextlib
import ctypes
import json
import os
import re
import subprocess
import tempfile
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import harness_config

ROOT = harness_config.ROOT
_ALL = harness_config.load()
_CFG = _ALL["slots"]
WORKTREE_BASE = harness_config.resolve(_ALL["worktree_base"])
PRODUCTS = tuple(_CFG["products"])
LAYERS = tuple(_CFG["layers"])
EXTRA = tuple(_CFG.get("extra", ()))
MAX_LIVE = _CFG["max_live"]
MAX_LIVE_SERVER = _CFG["max_live_server"]
LOCK = ".slot-lock"


def _alt(names: tuple[str, ...]) -> str:
    return "|".join(map(re.escape, names)) or "(?!)"  # 빈 목록 = 어떤 이름도 안 맞음


def parse_slot(name: str) -> tuple[str, str | None]:
    """허용 이름과 선택적 -2..-9 접미만 받는다."""
    pattern = rf"(?:({_alt(PRODUCTS)})-({_alt(LAYERS)})|({_alt(EXTRA)}))"
    match = re.fullmatch(pattern + r"(?:-[2-9])?", name)
    if match:
        return match[1] or match[3], match[2]
    raise ValueError(
        f"Invalid slot {name!r}; allowed: <product>-<layer> or {', '.join(EXTRA)}; "
        f"products: {', '.join(PRODUCTS)}; layers: {', '.join(LAYERS)}; suffix: -2..-9"
    )


def slot_path(name: str, base: Path = WORKTREE_BASE) -> Path:
    parse_slot(name)
    return base / name


def read_lock(path: Path) -> dict | None:
    """슬롯 디렉터리의 잠금. 없으면 None, 읽기/형식 오류는 점유로 보존한다."""
    try:
        data = json.loads((path / LOCK).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, ValueError):
        return {"broken": True}
    if (
        not isinstance(data, dict)
        or not {"issue", "phase", "pid", "started_at"}.issubset(data)
        or type(data["pid"]) is not int
        or data["pid"] <= 0
    ):
        return {"broken": True}
    return data


def pid_alive(pid: int) -> bool:
    """판정 실패는 점유로 본다. Windows os.kill은 프로세스를 종료할 수 있어 쓰지 않는다."""
    if type(pid) is not int or pid <= 0:
        return True
    try:
        if os.name == "nt":
            from ctypes import wintypes

            kernel = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
            kernel.OpenProcess.restype = wintypes.HANDLE
            kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
            kernel.WaitForSingleObject.restype = wintypes.DWORD
            kernel.CloseHandle.argtypes = [wintypes.HANDLE]
            kernel.CloseHandle.restype = wintypes.BOOL
            if pid > 0xFFFFFFFF:
                return True
            handle = kernel.OpenProcess(0x00100000, False, pid)  # SYNCHRONIZE
            if not handle:
                return ctypes.get_last_error() != 87  # ERROR_INVALID_PARAMETER: no PID
            try:
                return kernel.WaitForSingleObject(handle, 0) != 0  # signaled = exited
            finally:
                kernel.CloseHandle(handle)
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except (OSError, OverflowError, ValueError):
        return True
    return True


def _occupied(lock: dict) -> bool:
    return bool(lock.get("broken")) or pid_alive(lock["pid"])


def _locks(base: Path) -> Iterator[tuple[str, dict]]:
    if not base.exists():
        return
    for path in sorted(base.iterdir()):
        try:
            parse_slot(path.name)
        except ValueError:
            continue
        if path.is_dir() and (lock := read_lock(path)) is not None:
            yield path.name, lock


def live_locks(base: Path) -> dict[str, dict]:
    return {name: lock for name, lock in _locks(base) if _occupied(lock)}


@contextlib.contextmanager
def _guard(base: Path) -> Iterator[None]:
    """검사→기록과 release를 직렬화한다. OS가 프로세스 종료 시 자동으로 해제한다."""
    base.mkdir(parents=True, exist_ok=True)
    # 이 파일은 유지한다. unlink하면 서로 다른 inode를 잠글 수 있다.
    with (base / ".slot-guard").open("a+b") as guard:
        if guard.tell() == 0:
            guard.write(b"\0")
            guard.flush()
        guard.seek(0)
        try:
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(guard.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(guard.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            raise RuntimeError("Slot registry busy; retry after the other operation") from error
        try:
            yield
        finally:
            guard.seek(0)
            if os.name == "nt":
                msvcrt.locking(guard.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(guard.fileno(), fcntl.LOCK_UN)


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, encoding="utf-8"
    )
    if result.returncode:
        raise RuntimeError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout


def _prepare(name: str, path: Path, repo: Path) -> None:
    if not path.exists():
        _git(repo, "worktree", "add", "--detach", str(path.resolve()), "origin/main")
    else:
        _git(path, "fetch", "origin")
    status = _git(path, "status", "--porcelain", "--untracked-files=all")
    if any(line[3:] != LOCK for line in status.splitlines()):
        raise RuntimeError(f"Slot {name} is dirty; preserve or commit the previous work first")


def open_slot(name: str, *, repo: Path, base: Path) -> Path:
    """잠금 없이 슬롯을 만들거나 최신화한다. 잠금은 execute.py 가 자기 PID 로 건다."""
    parse_slot(name)
    path = slot_path(name, base)
    with _guard(base):
        lock = read_lock(path)
        if lock is not None and _occupied(lock):
            raise RuntimeError(
                f"Slot {name} occupied: phase={lock.get('phase', '?')} pid={lock.get('pid', '?')}"
            )
        _prepare(name, path, repo)
    return path


def acquire(name: str, *, issue: int, phase: str, pid: int, repo: Path, base: Path) -> Path:
    _, layer = parse_slot(name)
    path = slot_path(name, base)
    if type(pid) is not int or pid <= 0:
        raise ValueError("pid must be a positive integer")
    with _guard(base):
        lock = read_lock(path)
        if lock is not None and _occupied(lock):
            raise RuntimeError(
                f"Slot {name} occupied: issue={lock.get('issue', '?')} "
                f"phase={lock.get('phase', '?')} pid={lock.get('pid', '?')} "
                f"broken={lock.get('broken', False)}"
            )
        live = live_locks(base)
        if len(live) + 1 > MAX_LIVE:
            raise RuntimeError(f"Live slot limit {MAX_LIVE} exceeded")
        servers = sum(parse_slot(slot)[1] == "server" for slot in live)
        if layer == "server" and servers + 1 > MAX_LIVE_SERVER:
            raise RuntimeError(f"Live server slot limit {MAX_LIVE_SERVER} exceeded")
        _prepare(name, path, repo)
        payload = {
            "issue": issue,
            "phase": phase,
            "pid": pid,
            "started_at": datetime.now(UTC).isoformat(),
        }
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=path, prefix=f"{LOCK}.", delete=False
            ) as stream:
                temporary = Path(stream.name)
                json.dump(payload, stream, ensure_ascii=False)
                stream.write("\n")
            os.replace(temporary, path / LOCK)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
    return path


def release(name: str, *, pid: int, base: Path) -> None:
    path = slot_path(name, base)
    if not base.exists():
        return
    with _guard(base):
        lock = read_lock(path)
        if lock is not None and not lock.get("broken") and lock["pid"] == pid:
            (path / LOCK).unlink()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    grab = commands.add_parser("acquire")
    grab.add_argument("slot")
    grab.add_argument("--issue", type=int, required=True)
    grab.add_argument("--phase", required=True)
    # 기본값 없음: Windows 에서 부모 PID 는 곧 끝나는 uv 라 잠금이 바로 죽은 것으로 보인다
    grab.add_argument("--pid", type=int, required=True, help="살아 있는 소유자 PID")
    drop = commands.add_parser("release")
    drop.add_argument("slot")
    drop.add_argument("--pid", type=int, required=True, help="acquire 때 쓴 PID")
    prep = commands.add_parser("open", help="잠금 없이 슬롯 준비(없으면 생성, 있으면 fetch)")
    prep.add_argument("slot")
    commands.add_parser("list")
    args = parser.parse_args()
    try:
        if args.command == "acquire":
            print(
                acquire(
                    args.slot,
                    issue=args.issue,
                    phase=args.phase,
                    pid=args.pid,
                    repo=ROOT,
                    base=WORKTREE_BASE,
                )
            )
        elif args.command == "open":
            print(open_slot(args.slot, repo=ROOT, base=WORKTREE_BASE))
        elif args.command == "release":
            release(args.slot, pid=args.pid, base=WORKTREE_BASE)
        else:
            print("slot\tissue\tphase\tpid\talive")
            for name, lock in _locks(WORKTREE_BASE):
                alive = "unknown (occupied)" if lock.get("broken") else str(pid_alive(lock["pid"]))
                print(
                    f"{name}\t{lock.get('issue', '?')}\t{lock.get('phase', '?')}\t"
                    f"{lock.get('pid', '?')}\t{alive}"
                )
    except (OSError, RuntimeError, ValueError) as error:
        parser.exit(1, f"ERROR: {error}\n")


if __name__ == "__main__":
    main()
