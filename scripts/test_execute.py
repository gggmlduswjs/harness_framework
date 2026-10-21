"""scripts/execute.py 하네스의 안전장치 테스트.

깨지면: 메인 체크아웃에서 권한 확인 없는 커밋이 돌거나(.env 포함), 금지 목록이 빠지거나,
cp949 로 한글 규칙을 못 읽거나, step 상태가 틀리게 기록되거나,
이슈·docs 근거 없는 phase 가 돈다.
실행: uv run pytest scripts/test_execute.py
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import execute
import slot


def test_engine_commands_keep_real_permission_boundaries():
    claude = execute.ENGINES["claude"]
    codex = execute.ENGINES["codex"]
    assert "--dangerously-skip-permissions" not in claude
    assert claude[claude.index("--permission-mode") + 1] == "dontAsk"
    assert "--dangerously-bypass-approvals-and-sandbox" not in codex
    assert codex[codex.index("--sandbox") + 1] == "workspace-write"
    assert 'approval_policy="never"' in codex
    assert "sandbox_workspace_write.network_access=false" in codex


@pytest.fixture(autouse=True)
def _config(monkeypatch):
    """harness.json 값과 무관하게 같은 슬롯 이름·가드레일·근거 규칙으로 검사한다."""
    monkeypatch.setattr(slot, "PRODUCTS", ("mall",))
    monkeypatch.setattr(slot, "LAYERS", ("front", "server"))
    monkeypatch.setattr(execute.StepExecutor, "GUARDRAIL_DOCS", ("CLAUDE.md", "docs/PRD.md"))
    monkeypatch.setattr(execute, "EVIDENCE", execute.re.compile(r"(?<![\w-])(docs/[\w./-]+\.md)"))
    monkeypatch.setattr(execute, "NOT_EVIDENCE", ("docs/ROADMAP.md",))


def _git(cwd: Path, *args: str) -> str:
    r = subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    return r.stdout


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "main"
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")
    _git(root, "commit", "-q", "--allow-empty", "-m", "init")
    return root


@pytest.fixture
def phase(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """phases/demo 에 step 0 하나짜리 index 를 만든 StepExecutor."""
    root = tmp_path / "proj"
    (root / "phases" / "demo").mkdir(parents=True)
    (root / "phases" / "demo" / "index.json").write_text(
        json.dumps(
            {
                "project": "데모",
                "phase": "demo",
                "steps": [{"step": 0, "name": "setup", "status": "pending"}],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(execute, "ROOT", root)
    ex = execute.StepExecutor("demo")
    monkeypatch.setattr(ex, "_commit_step", lambda *a: None)
    monkeypatch.setattr(ex, "_update_top_index", lambda *a: None)
    return ex


def _fake_claude(ex: execute.StepExecutor, **fields):
    def run(step, preamble):
        idx = ex._read_json(ex._index_file)
        idx["steps"][0].update(fields)
        ex._write_json(ex._index_file, idx)

    return run


# --- utf-8 · 가드레일 문서 ---


def test_guardrails_read_utf8_and_only_existing_docs(phase):
    root = execute.ROOT
    (root / "CLAUDE.md").write_bytes("# 규칙: 삭제하지 않는다".encode())
    (root / "docs").mkdir(parents=True)
    (root / "docs" / "PRD.md").write_bytes("문서 지도".encode())
    (root / "docs" / "DESIGN.md").write_text("넣지 않음", encoding="utf-8")

    g = phase._load_guardrails()

    assert "규칙: 삭제하지 않는다" in g and "문서 지도" in g
    assert "넣지 않음" not in g  # docs 전체가 아니라 정한 색인만


# --- worktree 강제 ---


def test_refuses_main_checkout_and_non_git(repo, tmp_path):
    assert "메인 체크아웃" in execute.worktree_error(repo)
    plain = tmp_path / "plain"
    plain.mkdir()
    assert execute.worktree_error(plain) is not None


def test_allows_linked_worktree(repo, tmp_path):
    wt = tmp_path / "wt"
    _git(repo, "worktree", "add", "-q", str(wt), "-b", "feat-demo")
    assert execute.worktree_error(wt) is None


def test_run_exits_before_anything_in_main_checkout(phase, monkeypatch):
    monkeypatch.setattr(execute, "worktree_error", lambda cwd: "ERROR: 메인 체크아웃")
    monkeypatch.setattr(phase, "_print_header", lambda: pytest.fail("헤더까지 가면 안 된다"))
    with pytest.raises(SystemExit) as e:
        phase.run()
    assert e.value.code == 1


# --- 슬롯 점유 · 재사용 브랜치 ---


@pytest.fixture
def slot_phase(repo, tmp_path, monkeypatch):
    phase_dir = repo / "phases" / "demo"
    phase_dir.mkdir(parents=True)
    (phase_dir / "index.json").write_text(
        json.dumps(
            {
                "phase": "demo",
                "issue": 756,
                "steps": [{"step": 0, "name": "setup", "status": "pending"}],
            }
        ),
        encoding="utf-8",
    )
    (phase_dir / "step0.md").write_text("docs/spec.md", encoding="utf-8")
    (repo / "docs").mkdir()
    (repo / "docs" / "spec.md").write_text("spec", encoding="utf-8")
    (repo / ".gitignore").write_text(".slot-lock\n", encoding="utf-8")
    _git(
        repo, "add", "phases/demo/index.json", "phases/demo/step0.md", "docs/spec.md", ".gitignore"
    )
    _git(repo, "commit", "-q", "-m", "phase fixture")
    origin = tmp_path / "origin.git"
    _git(tmp_path, "clone", "-q", "--bare", str(repo), str(origin))
    _git(repo, "remote", "add", "origin", str(origin))
    _git(repo, "fetch", "origin")
    base = tmp_path / "slots"
    root = base / "mall-front"
    _git(repo, "worktree", "add", "-q", "-b", "previous", str(root), "origin/main")
    monkeypatch.setattr(execute, "ROOT", root)
    monkeypatch.setattr(execute, "WORKTREE_BASE", base)
    ex = execute.StepExecutor("demo")
    monkeypatch.setattr(ex, "_commit_step", lambda *a: None)
    return ex


@pytest.mark.parametrize("failure_at", ["_invoke_claude", "_finalize"])
@pytest.mark.parametrize("error", [RuntimeError("step failed"), SystemExit(2)])
def test_slot_released_even_when_execution_or_finalize_raises(
    slot_phase, monkeypatch, failure_at, error
):
    root = Path(slot_phase._root)

    def fail(*args):
        lock = slot.read_lock(root)
        assert lock is not None
        assert (lock["issue"], lock["phase"], lock["pid"]) == (756, "demo", os.getpid())
        raise error

    monkeypatch.setattr(slot_phase, "_invoke_claude", _fake_claude(slot_phase, status="completed"))
    monkeypatch.setattr(slot_phase, failure_at, fail)
    with pytest.raises(type(error)) as caught:
        slot_phase.run()
    assert caught.value is error
    assert not (root / slot.LOCK).exists()


def test_live_slot_owner_blocks_all_steps(slot_phase, monkeypatch, capsys):
    root = Path(slot_phase._root)
    # The parent process remains alive for this test and differs from the harness PID.
    owner = os.getppid()
    assert owner != os.getpid() and slot.pid_alive(owner)
    slot.acquire(root.name, issue=755, phase="previous", pid=owner, repo=root, base=root.parent)
    before = (root / slot.LOCK).read_bytes()
    index_before = slot_phase._index_file.read_bytes()
    monkeypatch.setattr(
        slot_phase, "_invoke_claude", lambda *a: pytest.fail("occupied slot ran a step")
    )
    try:
        with pytest.raises(SystemExit) as caught:
            slot_phase.run()
        assert caught.value.code == 1
        assert "occupied" in capsys.readouterr().out
        assert (root / slot.LOCK).read_bytes() == before
        assert slot_phase._index_file.read_bytes() == index_before
        assert _git(root, "branch", "--show-current").strip() == "previous"
    finally:
        slot.release(root.name, pid=owner, base=root.parent)


def test_new_branch_starts_at_fetched_origin_main_not_previous_head(slot_phase, repo):
    root = Path(slot_phase._root)
    _git(root, "commit", "-q", "--allow-empty", "-m", "previous work")
    previous = _git(root, "rev-parse", "HEAD")
    # Advance only the local remote so omitting fetch also fails this regression.
    origin = Path(_git(repo, "remote", "get-url", "origin").strip())
    tip = _git(origin, "commit-tree", "main^{tree}", "-p", "main", "-m", "new main").strip()
    _git(origin, "update-ref", "refs/heads/main", tip)

    slot_phase._checkout_branch()

    assert _git(root, "branch", "--show-current").strip() == "feat-demo"
    assert _git(root, "rev-parse", "HEAD").strip() == tip
    assert _git(root, "rev-parse", "HEAD") != previous
    assert _git(root, "rev-parse", "previous") == previous


def test_failed_fetch_does_not_create_branch_from_stale_main(slot_phase, repo, tmp_path):
    root = Path(slot_phase._root)
    _git(repo, "remote", "set-url", "origin", str(tmp_path / "missing-origin.git"))
    with pytest.raises(SystemExit) as caught:
        slot_phase._checkout_branch()
    assert caught.value.code == 1
    assert _git(root, "branch", "--show-current").strip() == "previous"
    assert not _git(root, "branch", "--list", "feat-demo").strip()


@pytest.mark.parametrize("valid_name", [False, True])
def test_non_slot_worktree_warns_and_still_runs(slot_phase, repo, monkeypatch, capsys, valid_name):
    root = Path(slot_phase._root)
    if valid_name:
        # A valid name outside WORKTREE_BASE is still not a managed slot.
        monkeypatch.setattr(execute, "WORKTREE_BASE", root.parent / "elsewhere")
    else:
        legacy = root.parent / "old-phase"
        _git(repo, "worktree", "add", "-q", "-b", "legacy", str(legacy), "origin/main")
        monkeypatch.setattr(execute, "ROOT", legacy)
        slot_phase = execute.StepExecutor("demo")
        monkeypatch.setattr(slot_phase, "_commit_step", lambda *a: None)
    monkeypatch.setattr(slot_phase, "_invoke_claude", _fake_claude(slot_phase, status="completed"))
    monkeypatch.setattr(slot_phase, "_finalize", lambda: None)
    slot_phase.run()
    assert slot_phase._read_json(slot_phase._index_file)["steps"][0]["status"] == "completed"
    assert capsys.readouterr().out.count("WARN: 슬롯 밖 worktree") == 1
    assert not (Path(slot_phase._root) / slot.LOCK).exists()


# --- 근거 강제: 이슈 번호 · docs 근거 ---


def test_refuses_phase_without_issue_number(phase):
    (phase._phase_dir / "step0.md").write_text("- /docs/specs/login.md", encoding="utf-8")
    err = execute.evidence_error(phase._phase_dir, execute.StepExecutor.GUARDRAIL_DOCS)
    assert err and "이슈 번호" in err


def test_refuses_phase_without_steps(phase):
    f = phase._phase_dir / "index.json"
    f.write_text(json.dumps({"phase": "demo", "issue": 1, "steps": []}), encoding="utf-8")
    err = execute.evidence_error(phase._phase_dir, execute.StepExecutor.GUARDRAIL_DOCS)
    assert err and "steps 가 비었다" in err


def test_refuses_step_without_docs_evidence(phase):
    idx = phase._read_json(phase._index_file)
    phase._write_json(phase._index_file, {**idx, "issue": 151})
    step = phase._phase_dir / "step0.md"
    spec = execute.ROOT / "docs" / "specs" / "login.md"
    for rel in ("docs/PRD.md", "docs/ROADMAP.md"):
        (execute.ROOT / rel).parent.mkdir(parents=True, exist_ok=True)
        (execute.ROOT / rel).write_text("x", encoding="utf-8")
    step.write_text("- /CLAUDE.md\n- /docs/PRD.md\n- /docs/ROADMAP.md", encoding="utf-8")
    err = execute.evidence_error(phase._phase_dir, execute.StepExecutor.GUARDRAIL_DOCS)
    assert err and "step0.md" in err  # 가드레일·진행 문서만으로는 근거가 아니다
    step.write_text("- /docs/PRD.md\n- /docs/specs/login.md", encoding="utf-8")
    err = execute.evidence_error(phase._phase_dir, execute.StepExecutor.GUARDRAIL_DOCS)
    assert err and "step0.md" in err  # 레포에 없는 경로(지어낸 근거)는 근거가 아니다
    spec.parent.mkdir(parents=True, exist_ok=True)
    spec.write_text("화면 명세", encoding="utf-8")
    assert execute.evidence_error(phase._phase_dir, execute.StepExecutor.GUARDRAIL_DOCS) is None


# --- 금지 목록 ---


def test_forbidden_list_prepended_to_every_step_prompt(phase):
    pre = phase._build_preamble("가드레일", "", prev_error="이전 에러")
    assert pre.startswith(execute.FORBIDDEN)
    for item in ("운영 DB 쓰기", "마이그레이션 적용", "머지", "push", "git add -A", ".env"):
        assert item in execute.FORBIDDEN


# --- 커밋: 이름으로만 add ---


def test_stage_adds_by_name_never_dash_a_and_skips_secrets(repo, monkeypatch):
    for rel in (
        "a.py",
        "한글.md",
        ".env",
        ".env.local",
        "apps/api/.env.production.local",
        ".env.example",
        "apps/web/.env.mock",
        "logs/x.log",
        "pkg/__pycache__/c.pyc",
        "web/node_modules/m.js",
        ".claude/audit.jsonl",
        "phases/demo/index.json",
    ):
        p = repo / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("x", encoding="utf-8")
    monkeypatch.setattr(execute, "ROOT", repo)
    ex = execute.StepExecutor.__new__(execute.StepExecutor)
    ex._root = str(repo)
    calls = []
    real = ex._run_git
    monkeypatch.setattr(ex, "_run_git", lambda *a: calls.append(a) or real(*a))

    ex._stage_changes("phases/demo/index.json")

    staged = _git(repo, "-c", "core.quotepath=false", "diff", "--cached", "--name-only").split()
    # 비밀 .env 는 빠지고, 커밋된 예시·mock 파일은 들어간다
    assert sorted(staged) == [".env.example", "a.py", "apps/web/.env.mock", "한글.md"]
    adds = [c for c in calls if c[0] == "add"]
    assert adds and all(c[1] == "--" and "-A" not in c and "." not in c for c in adds)


# --- 상태 전이 ---


def test_completed_records_timestamp(phase, monkeypatch):
    monkeypatch.setattr(
        phase, "_invoke_claude", _fake_claude(phase, status="completed", summary="뼈대")
    )
    assert phase._execute_single_step({"step": 0, "name": "setup"}, "") is True
    s = phase._read_json(phase._index_file)["steps"][0]
    assert s["status"] == "completed" and "completed_at" in s


def test_failed_engine_cannot_report_completed(phase, monkeypatch):
    def fail(step, preamble):
        _fake_claude(phase, status="completed", summary="unverified")(step, preamble)
        return {"exitCode": 1}

    monkeypatch.setattr(phase, "_invoke_claude", fail)
    with pytest.raises(SystemExit) as error:
        phase._execute_single_step({"step": 0, "name": "setup"}, "")
    assert error.value.code == 1
    state = phase._read_json(phase._index_file)["steps"][0]
    assert state["status"] == "error" and "engine exit code 1" in state["error_message"]
    assert "completed_at" not in state and "summary" not in state


def test_blocked_exits_2(phase, monkeypatch):
    monkeypatch.setattr(
        phase, "_invoke_claude", _fake_claude(phase, status="blocked", blocked_reason="API 키")
    )
    with pytest.raises(SystemExit) as e:
        phase._execute_single_step({"step": 0, "name": "setup"}, "")
    assert e.value.code == 2
    assert "blocked_at" in phase._read_json(phase._index_file)["steps"][0]


def test_error_retries_then_exits_1(phase, monkeypatch):
    calls = []

    def fail(step, preamble):
        calls.append(preamble)
        _fake_claude(phase, status="error", error_message="테스트 실패")(step, preamble)

    monkeypatch.setattr(phase, "_invoke_claude", fail)
    with pytest.raises(SystemExit) as e:
        phase._execute_single_step({"step": 0, "name": "setup"}, "")
    assert e.value.code == 1 and len(calls) == execute.StepExecutor.MAX_RETRIES
    assert "테스트 실패" in calls[1]  # 이전 에러를 다음 시도에 넘긴다
    s = phase._read_json(phase._index_file)["steps"][0]
    assert s["status"] == "error" and "failed_at" in s


# --- 엔진 호출 ---


def _grandchild_engine(sleep_s: int) -> list[str]:
    """출력은 바로 끝내지만 stdout 을 물려받은 손자가 sleep_s 초 남는 엔진(Gradle 데몬 흉내)."""
    code = (
        "import subprocess,sys;"
        f"subprocess.Popen([sys.executable,'-c','import time;time.sleep({sleep_s})']);"
        "print('done')"
    )
    return [sys.executable, "-c", code]


def test_invoke_returns_when_grandchild_holds_stdout(phase, monkeypatch):
    # 깨지면: 엔진이 띄운 Gradle 데몬이 파이프를 물어 하네스가 영영 멈춘다
    # (실측 31분 멈춤).
    monkeypatch.setitem(execute.ENGINES, "claude", _grandchild_engine(20))
    (phase._phase_dir / "step0.md").write_text("x", encoding="utf-8")
    t = time.monotonic()
    out = phase._invoke_claude({"step": 0, "name": "setup"}, "")
    assert time.monotonic() - t < 10
    assert out["exitCode"] == 0 and "done" in out["stdout"]


def test_invoke_timeout_records_error_instead_of_crashing(phase, monkeypatch):
    # 깨지면: 시간 초과가 TimeoutExpired 로 하네스 전체를 죽이고 index 기록·재시도가 안 된다.
    sleeper = [sys.executable, "-c", "import time;time.sleep(30)"]
    monkeypatch.setitem(execute.ENGINES, "claude", sleeper)
    monkeypatch.setattr(execute, "ENGINE_TIMEOUT_S", 1)
    (phase._phase_dir / "step0.md").write_text("x", encoding="utf-8")
    out = phase._invoke_claude({"step": 0, "name": "setup"}, "")
    assert out["exitCode"] != 0 and "timeout" in out["stderr"]


def test_compact_codex_keeps_failure_events():
    # 깨지면: 축소된 codex step 출력에서 실패 원인이 사라져 재시도·진단을 못 한다.
    noise = json.dumps({"type": "item.completed", "item": {"type": "command_execution"}})
    error = json.dumps({"type": "error", "message": "stream disconnected"})
    failed = json.dumps({"type": "turn.failed", "error": {"message": "quota exceeded"}})
    out = execute._compact_codex(f"{noise}\n{error}\n{noise}\n{failed}", 0)
    assert out.splitlines() == [error, failed]  # 정상 종료면 원문 꼬리 없이 실패 줄만
    assert "[harness] raw tail:" in execute._compact_codex(noise, 1)


def test_engine_killed_before_exception_escapes(monkeypatch: pytest.MonkeyPatch):
    """깨지면 Ctrl+C 뒤 슬롯 잠금이 풀린 채 엔진이 계속 써서 다음 줄기와 같은 checkout 을 덮는다."""
    killed = []

    class Proc:
        pid = 1

        def wait(self, timeout=None):
            raise KeyboardInterrupt

    monkeypatch.setattr(execute.subprocess, "Popen", lambda *a, **k: Proc())
    monkeypatch.setattr(execute, "_kill_tree", killed.append)
    with pytest.raises(KeyboardInterrupt):
        execute._run_engine(["engine"], "prompt", ".")
    assert len(killed) == 1
