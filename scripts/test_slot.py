"""깨지면 두 세션이 슬롯을 덮어쓰거나 worktree 점유가 상한 없이 늘어난다."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import slot


@pytest.fixture(autouse=True)
def _names(monkeypatch):
    """harness.json 값과 무관하게 같은 이름·상한으로 검사한다."""
    monkeypatch.setattr(slot, "PRODUCTS", ("mall", "pos"))
    monkeypatch.setattr(slot, "LAYERS", ("front", "server", "agent"))
    monkeypatch.setattr(slot, "EXTRA", ("ops",))
    monkeypatch.setattr(slot, "MAX_LIVE", 8)
    monkeypatch.setattr(slot, "MAX_LIVE_SERVER", 2)


def _git(cwd: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    return result.stdout


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "main"
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")
    (root / "tracked.txt").write_text("original\n", encoding="utf-8")
    _git(root, "add", "tracked.txt")
    _git(root, "commit", "-q", "-m", "init")
    # A local bare origin: no network, real checkout or push involved.
    origin = tmp_path / "origin.git"
    _git(tmp_path, "clone", "-q", "--bare", str(root), str(origin))
    _git(root, "remote", "add", "origin", str(origin))
    _git(root, "fetch", "origin")
    return root


def _lock(base: Path, name: str, pid: int) -> Path:
    path = base / name
    path.mkdir(parents=True, exist_ok=True)
    (path / slot.LOCK).write_text(
        json.dumps({"issue": 756, "phase": "previous", "pid": pid, "started_at": "past"}),
        encoding="utf-8",
    )
    return path


def _acquire(repo: Path, base: Path, name: str = "mall-front") -> Path:
    return slot.acquire(name, issue=757, phase="next", pid=os.getpid(), repo=repo, base=base)


@pytest.mark.parametrize("broken", [False, True])
def test_occupied_lock_is_never_overwritten(repo, tmp_path, broken):
    base = tmp_path / "slots"
    path = _lock(base, "mall-front", os.getpid())
    if broken:
        (path / slot.LOCK).write_text("{broken", encoding="utf-8")
        assert slot.read_lock(path) == {"broken": True}
    before = (path / slot.LOCK).read_bytes()
    with pytest.raises(RuntimeError) as error:
        _acquire(repo, base)
    if not broken:
        for value in ("756", "previous", str(os.getpid())):
            assert value in str(error.value)
    assert (path / slot.LOCK).read_bytes() == before
    assert "mall-front" in slot.live_locks(base)


def test_dead_lock_can_be_replaced_without_resetting_worktree(repo, tmp_path):
    base = tmp_path / "slots"
    path = _acquire(repo, base)
    _git(path, "switch", "-c", "previous-work")
    _git(path, "commit", "-q", "--allow-empty", "-m", "preserve")
    head = _git(path, "rev-parse", "HEAD")
    child = subprocess.Popen([sys.executable, "-c", "pass"])
    child.wait(timeout=10)
    _lock(base, "mall-front", child.pid)
    assert not slot.pid_alive(child.pid)
    assert slot.live_locks(base) == {}
    assert _acquire(repo, base) == path
    lock = slot.read_lock(path)
    assert lock is not None
    assert (lock["issue"], lock["phase"], lock["pid"]) == (757, "next", os.getpid())
    assert lock["started_at"] != "past"
    assert _git(path, "rev-parse", "HEAD") == head
    assert _git(path, "branch", "--show-current").strip() == "previous-work"


@pytest.mark.parametrize(
    ("occupied", "requested", "limit"),
    [
        (["mall-front", *[f"mall-front-{i}" for i in range(2, 9)]], "ops", "8"),
        (["mall-server", "mall-server-2"], "pos-server", "2"),
    ],
)
def test_live_limits_reject_before_creating_worktree(repo, tmp_path, occupied, requested, limit):
    base = tmp_path / "slots"
    for name in occupied:
        _lock(base, name, os.getpid())
    with pytest.raises(RuntimeError, match=limit):
        _acquire(repo, base, requested)
    assert not (base / requested).exists()


@pytest.mark.parametrize("dirty", ["tracked", "lock-prefix"])
def test_dirty_slot_rejected_without_lock_or_work_changes(repo, tmp_path, dirty):
    base = tmp_path / "slots"
    path = _acquire(repo, base)
    slot.release("mall-front", pid=os.getpid(), base=base)
    filename = {"tracked": "tracked.txt", "lock-prefix": ".slot-lock-notes"}.get(dirty, "new.txt")
    (path / filename).write_text("unfinished", encoding="utf-8")
    if dirty == "staged":
        _git(path, "add", filename)
    before = _git(path, "status", "--porcelain")
    with pytest.raises(RuntimeError, match="dirty"):
        _acquire(repo, base)
    assert slot.read_lock(path) is None
    assert _git(path, "status", "--porcelain") == before
    assert (path / filename).read_text(encoding="utf-8") == "unfinished"


def test_parse_slot_names():
    assert slot.parse_slot("pos-agent-9") == ("pos", "agent")
    assert slot.parse_slot("ops-2") == ("ops", None)


def test_invalid_slot_never_becomes_a_path(tmp_path):
    for name in ("", "unknown-front", "mall-back", "../ops", "mall/front", "mall-front-10"):
        with pytest.raises(ValueError):
            slot.slot_path(name, tmp_path)


def test_release_only_removes_owner_lock(tmp_path):
    path = _lock(tmp_path, "mall-front", os.getpid())
    before = (path / slot.LOCK).read_bytes()
    slot.release("mall-front", pid=os.getpid() + 1, base=tmp_path)
    assert (path / slot.LOCK).read_bytes() == before
    slot.release("mall-front", pid=os.getpid(), base=tmp_path)
    assert slot.read_lock(path) is None
    slot.release("mall-front", pid=os.getpid(), base=tmp_path)


def test_overlapping_acquire_cannot_claim_same_slot(repo, tmp_path, monkeypatch):
    base = tmp_path / "slots"
    original = slot.live_locks

    def competing_acquire(directory):
        # A separate CLI process enters while the first is between check and write.
        code = (
            "import sys; from pathlib import Path; sys.path.insert(0, sys.argv[4]); import slot; "
            "slot.PRODUCTS = ('mall',); "
            "slot.acquire('mall-front', issue=758, phase='rival', pid=int(sys.argv[3]), "
            "repo=Path(sys.argv[1]), base=Path(sys.argv[2]))"
        )
        result = subprocess.run(
            [sys.executable, "-c", code, str(repo), str(base), str(os.getpid()), str(Path(slot.__file__).parent)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=10,
        )
        assert result.returncode != 0
        assert "busy" in result.stderr
        return original(directory)

    monkeypatch.setattr(slot, "live_locks", competing_acquire)
    path = _acquire(repo, base)
    assert slot.read_lock(path)["phase"] == "next"
