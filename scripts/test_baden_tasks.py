"""baden_tasks.py 핵심: 깨지면 커밋 ↔ Baden 작업 연결이 조용히 빠지거나, 훅이 커밋을 막는다.

- 상태 파일은 worktree 별 git-dir, 넣기·빼기·중복 없음.
- prepare-commit-msg: 모든 id 트레일러, 이미 있으면 중복 없음, 파일 없으면 메시지 그대로, 실제 커밋 성공.
- baden_start_task 실제 응답 모양(MCP content 배열 안 JSON 문자열)에서 taskId 를 꺼낸다.
실행: uv run --no-project --with pytest python -m pytest scripts/test_baden_tasks.py -q
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).parent
SCRIPT = HERE / "baden_tasks.py"
sys.path.insert(0, str(HERE))
import baden_tasks  # noqa: E402

T1 = "846ecd94-9c5c-46ea-9c0f-8ba06b8d7c4e"
T2 = "harness-0-mvp"


def git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True).stdout


def run(cwd, *args, stdin=None):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args], cwd=cwd, input=stdin, capture_output=True, text=True, encoding="utf-8"
    )


@pytest.fixture
def repo(tmp_path):
    r = tmp_path / "repo"
    r.mkdir()
    git(r, "init", "-q")
    git(r, "config", "user.email", "t@t")
    git(r, "config", "user.name", "t")
    git(r, "commit", "-q", "--allow-empty", "-m", "init")
    return r


def test_add_remove_dedupe_per_worktree(repo, tmp_path):
    baden_tasks.add(T1, repo)
    baden_tasks.add(T1, repo)
    baden_tasks.add(T2, repo)
    assert baden_tasks.read_ids(repo) == [T1, T2]
    assert baden_tasks.state_file(repo) == Path(git(repo, "rev-parse", "--absolute-git-dir").strip()) / "baden-tasks"
    wt = tmp_path / "wt"
    git(repo, "worktree", "add", "-q", str(wt))
    assert baden_tasks.read_ids(wt) == []  # 다른 worktree 와 안 섞인다
    baden_tasks.remove(T1, repo)
    assert baden_tasks.read_ids(repo) == [T2]


def test_start_and_complete_hook_payload(repo):
    # ibare/baden mcp/src/index.ts: content=[{type:'text', text: JSON.stringify({taskId})}]
    start = {
        "tool_name": "mcp__baden__baden_start_task",
        "tool_input": {"prompt": "x", "projectName": "p"},
        "tool_response": [{"type": "text", "text": json.dumps({"taskId": T1})}],
        "cwd": str(repo),
    }
    assert run(repo, "hook", stdin=json.dumps(start)).returncode == 0
    assert baden_tasks.read_ids(repo) == [T1]
    done = {"tool_name": "mcp__baden__baden_complete_task", "tool_input": {"taskId": T1, "summary": "s"}, "cwd": str(repo)}
    assert run(repo, "hook", stdin=json.dumps(done)).returncode == 0
    assert baden_tasks.read_ids(repo) == []
    # 모양이 달라도: 그냥 문자열 · 서버 꺼짐 fallback(id 없음)
    assert baden_tasks.task_id_from_response(f"taskId is {T1}") == T1
    assert baden_tasks.task_id_from_response([{"type": "text", "text": '{"ok":true,"source":"fallback"}'}]) is None


def test_commit_msg_trailers(repo):
    msg = repo / "MSG"
    msg.write_text("feat: x\n", encoding="utf-8")
    run(repo, "commit-msg", str(msg))
    assert msg.read_text(encoding="utf-8") == "feat: x\n"  # 파일 없으면 그대로

    baden_tasks.add(T1, repo)
    baden_tasks.add(T2, repo)
    msg.write_text(f"feat: x\n\nBaden-Task: {T1}\n", encoding="utf-8")
    assert run(repo, "commit-msg", str(msg)).returncode == 0
    body = msg.read_text(encoding="utf-8")
    assert body.count(f"Baden-Task: {T1}") == 1
    assert body.count(f"Baden-Task: {T2}") == 1


@pytest.mark.skipif(not shutil.which("uv"), reason="훅이 uv 로 python 을 부른다")
def test_real_commit_with_hookspath(repo):
    (repo / "scripts" / "githooks").mkdir(parents=True)
    shutil.copy(SCRIPT, repo / "scripts" / "baden_tasks.py")
    shutil.copy(HERE / "githooks" / "prepare-commit-msg", repo / "scripts" / "githooks" / "prepare-commit-msg")
    assert run(repo, "install").returncode == 0
    assert git(repo, "config", "core.hooksPath").strip() == "scripts/githooks"
    baden_tasks.add(T1, repo)
    git(repo, "commit", "-q", "--allow-empty", "-m", "feat: y")
    assert f"Baden-Task: {T1}" in git(repo, "log", "-1", "--format=%B")
    # 다른 hooksPath 는 덮지 않는다
    git(repo, "config", "core.hooksPath", "other")
    assert "core.hooksPath=other" in run(repo, "install").stdout
    assert git(repo, "config", "core.hooksPath").strip() == "other"
