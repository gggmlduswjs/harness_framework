#!/usr/bin/env python3
"""Stop — 지금 잡은 GitHub 이슈에 handoff 코멘트(한 일 / 멈춘 곳 / 다음 할 일 / 브랜치·PR)를 남긴다.

잡은 이슈: 브랜치 `<type>/<N>-<slug>` 의 N, 없으면 `.claude/current-issue` 파일의 숫자
(main 브랜치에서는 파일 폴백을 쓰지 않는다). 둘 다 없으면 조용히 끝낸다.
같은 이슈에는 60분 안에 다시 달지 않고, HEAD 가 그대로여도 달지 않는다
(`.claude/.handoff-stamp`, gitignore).
git·gh 호출은 하나당 5초, 전체 15초. 실패해도 세션을 막지 않는다(항상 exit 0).
/briefing 은 MARK 로 이 코멘트를 찾는다.
원본: bigsix scripts/hooks/issue_handoff.py
"""

import contextlib
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

MARK = "<!-- issue-handoff -->"
GAP = 3600  # 초
CALL_TIMEOUT = 5
BUDGET = 15
FAIL = "조회 실패"
BRANCH_ISSUE = re.compile(r"^(?:feat|fix|chore|docs|refactor|test)/(\d+)-(?!\d)")
_deadline = time.monotonic() + BUDGET


def sh(cmd: list[str], root: Path, stdin: str | None = None) -> tuple[str | None, str]:
    """(stdout, stderr). 실패하면 stdout 이 None — 「결과 없음」("")과 구분한다."""
    left = min(CALL_TIMEOUT, _deadline - time.monotonic())
    if left <= 0:
        return None, "시간 예산 초과"
    try:
        r = subprocess.run(
            cmd,
            cwd=root,
            input=stdin,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=left,
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        return None, str(e)
    return (r.stdout.strip() if r.returncode == 0 else None), r.stderr


def run(cmd: list[str], root: Path, stdin: str | None = None) -> str | None:
    return sh(cmd, root, stdin)[0]


def issue_number(branch: str | None, root: Path) -> str | None:
    if branch and (m := BRANCH_ISSUE.match(branch)):
        return m.group(1)
    if branch in ("main", "master"):
        return None
    f = root / ".claude" / "current-issue"
    if f.exists():
        m = re.search(r"\d+", f.read_text(encoding="utf-8"))
        return m.group(0) if m else None
    return None


def _load(stamp: Path) -> dict:
    try:
        return json.loads(stamp.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def should_post(stamp: Path, issue: str, head: str, now: float) -> bool:
    """60분이 지났고 HEAD 가 바뀌었을 때만."""
    last = _load(stamp).get(issue, {})
    return now - last.get("at", float("-inf")) >= GAP and last.get("sha") != head


def mark_posted(stamp: Path, issue: str, head: str, now: float) -> dict:
    """찍고, 되돌릴 때 쓸 이전 내용을 돌려준다."""
    data = _load(stamp)
    before = dict(data)
    data[issue] = {"at": now, "sha": head}
    stamp.write_text(json.dumps(data), encoding="utf-8")
    return before


def build_body(root: Path, branch: str | None, sh=sh) -> str:
    """git·gh 가 실패한 칸은 「조회 실패」로 쓴다(「없음」·「깨끗함」으로 숨기지 않는다)."""
    log, _ = sh(["git", "log", "--oneline", "-5", "origin/main..HEAD"], root)
    status, _ = sh(["git", "status", "--short"], root)
    pr, pr_err = sh(
        [
            "gh",
            "pr",
            "view",
            "--json",
            "number,url,state",
            "-q",
            r'"#\(.number) \(.state) \(.url)"',
        ],
        root,
    )
    commits = FAIL if log is None else (log or "(새 커밋 없음)")
    dirty = [ln for ln in (status or "").splitlines() if ln]
    if pr is None and "no pull requests found" in pr_err:
        pr = ""
    if status is None or pr is None:
        nxt = f"{FAIL} — 직접 확인"
    elif dirty:
        nxt = f"커밋 안 된 변경 {len(dirty)}개 정리·커밋"
    elif not pr:
        nxt = "PR 만들기(`Closes #N`)"
    else:
        nxt = "리뷰·CI 확인(`gh pr checks`)"
    stopped = "\n".join(dirty[:10]) + (f"\n… 외 {len(dirty) - 10}개" if len(dirty) > 10 else "")
    return (
        f"{MARK}\n### handoff ({time.strftime('%Y-%m-%d %H:%M')})\n"
        f"**한 일(최근 커밋)**\n```\n{commits}\n```\n"
        f"**멈춘 곳(git status)**\n```\n{FAIL if status is None else stopped or '깨끗함'}\n```\n"
        f"**다음 할 일** {nxt}\n\n"
        f"**브랜치·PR** `{branch or '?'}` · {FAIL if pr is None else pr or 'PR 없음'}\n"
    )


def main() -> None:
    root = Path(os.environ.get("CLAUDE_PROJECT_DIR") or ".").resolve()
    branch = run(["git", "branch", "--show-current"], root)
    issue = issue_number(branch, root)
    if not issue:
        return
    head = run(["git", "rev-parse", "HEAD"], root)
    stamp = root / ".claude" / ".handoff-stamp"
    now = time.time()
    if not head or not should_post(stamp, issue, head, now):
        return
    body = build_body(root, branch)
    # 게시 전에 먼저 찍는다 — 훅이 게시 직후 끊겨도 중복 코멘트가 생기지 않게. 실패하면 되돌린다.
    before = mark_posted(stamp, issue, head, now)
    if run(["gh", "issue", "comment", issue, "--body-file", "-"], root, stdin=body) is None:
        stamp.write_text(json.dumps(before), encoding="utf-8")


if __name__ == "__main__":
    with contextlib.suppress(Exception):  # 훅은 세션을 막지 않는다
        main()
    sys.exit(0)
