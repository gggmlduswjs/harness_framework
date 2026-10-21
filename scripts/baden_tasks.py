"""커밋 트레일러 `Baden-Task: <task_id>` — 활성 Baden task 목록을 파일로 들고 커밋마다 붙인다.

설계 원본: ibare/baden docs/git-client-baden-integration.md 「연결 설계」 1~3.
- 상태 파일 `<git-dir>/baden-tasks` — worktree 마다 git-dir 이 달라 병렬 worktree 끼리 안 섞인다. 한 줄 한 id.
- 넣기: PostToolUse `baden_start_task` 응답의 taskId(규칙이 아니라 훅 — 에이전트가 잊어도 빠지지 않는다).
  execute.py 도 실행 시작에 `harness-<phase>` 를 넣는다.
- 빼기: PostToolUse `baden_complete_task` 의 tool_input.taskId. 커밋마다 비우지 않는다(task 하나 = 커밋 여럿, N:M).
- 커밋: scripts/githooks/prepare-commit-msg → `commit-msg <file>`. source(merge·squash·amend) 구분 없이 붙이고
  `addIfDifferent` 로 이미 있는 같은 줄은 건너뛴다. 어떤 실패도 커밋을 막지 않는다(exit 0).

사용:
  python scripts/baden_tasks.py hook            # PostToolUse(stdin JSON)
  python scripts/baden_tasks.py add|remove <id>
  python scripts/baden_tasks.py commit-msg <msgfile>
  python scripts/baden_tasks.py install         # SessionStart: core.hooksPath 비어 있으면 scripts/githooks
"""

import json
import re
import subprocess
import sys
from pathlib import Path

HOOKS_PATH = "scripts/githooks"
UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.I)


def _git(cwd, *args) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, encoding="utf-8", check=True
    ).stdout.strip()


def state_file(cwd=None) -> Path:
    return Path(_git(cwd, "rev-parse", "--absolute-git-dir")) / "baden-tasks"


def read_ids(cwd=None) -> list[str]:
    f = state_file(cwd)
    if not f.exists():
        return []
    return list(dict.fromkeys(x.strip() for x in f.read_text(encoding="utf-8").splitlines() if x.strip()))


def _write(cwd, ids) -> None:
    state_file(cwd).write_text("".join(f"{i}\n" for i in ids), encoding="utf-8")


def add(task_id: str, cwd=None) -> None:
    ids = read_ids(cwd)
    if task_id not in ids:
        _write(cwd, [*ids, task_id])


def remove(task_id: str, cwd=None) -> None:
    ids = read_ids(cwd)
    if task_id in ids:
        _write(cwd, [i for i in ids if i != task_id])


def task_id_from_response(resp):
    """baden_start_task 응답에서 taskId. MCP 원본은 content=[{type:text, text:'{"taskId":"<uuid>"}'}]
    (ibare/baden mcp/src/tools.ts·index.ts). 모양이 달라도 JSON 을 파고들고, 마지막엔 UUID 정규식."""
    if isinstance(resp, str):
        try:
            return task_id_from_response(json.loads(resp))
        except ValueError:
            m = UUID.search(resp)
            return m.group(0) if m else None
    if isinstance(resp, dict) and isinstance(resp.get("taskId"), str):
        return resp["taskId"]
    if isinstance(resp, (dict, list)):
        for v in resp.values() if isinstance(resp, dict) else resp:
            found = task_id_from_response(v)
            if found:
                return found
    return None


def hook(payload: dict) -> None:
    name = payload.get("tool_name", "")
    cwd = payload.get("cwd") or None
    if name.endswith("baden_start_task"):
        tid = task_id_from_response(payload.get("tool_response"))
        if tid:
            add(tid, cwd)
    elif name.endswith("baden_complete_task"):
        tid = (payload.get("tool_input") or {}).get("taskId")
        if tid:
            remove(tid, cwd)


def commit_msg(msgfile: str) -> None:
    ids = read_ids()
    if not ids:
        return
    args = ["interpret-trailers", "--in-place", "--if-exists", "addIfDifferent"]
    for i in ids:
        args += ["--trailer", f"Baden-Task: {i}"]
    _git(None, *args, msgfile)


def install() -> None:
    try:
        cur = _git(None, "config", "core.hooksPath")
    except subprocess.CalledProcessError:  # 설정 없음 = exit 1
        cur = ""
    if not cur:
        _git(None, "config", "core.hooksPath", HOOKS_PATH)
    elif cur.replace("\\", "/").rstrip("/") != HOOKS_PATH:
        print(f"baden_tasks: core.hooksPath={cur} — {HOOKS_PATH}/prepare-commit-msg 를 거기서 불러야 Baden-Task 트레일러가 붙는다")


def main(argv) -> None:
    cmd = argv[0] if argv else ""
    if cmd == "hook":
        hook(json.load(sys.stdin))
    elif cmd == "add":
        add(argv[1])
    elif cmd == "remove":
        remove(argv[1])
    elif cmd == "commit-msg":
        commit_msg(argv[1])
    elif cmd == "install":
        install()


if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except Exception as e:  # 훅 — 무엇이 깨져도 도구 호출·커밋·세션을 막지 않는다
        print(f"baden_tasks: {e}", file=sys.stderr)
    sys.exit(0)
