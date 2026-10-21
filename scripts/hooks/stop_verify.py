"""Stop Verify — Stop. 바뀐 파일만 harness.json 「lint」 명령으로 빠르게 본다(최대 30초).

결과를 systemMessage 로 보여 줄 뿐 막지 않는다(항상 exit 0). 전체 테스트 스위트는 돌리지 않는다 — CI 몫.
lint.globs 에 맞는 바뀐 파일(git diff HEAD + 추적 안 된 새 파일)만 lint.command 뒤에 붙인다.
원본: bigsix scripts/hooks/stop-verify.sh (설정을 읽으려고 python 으로 옮겼다)
"""

import contextlib
import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import harness_config

TIMEOUT_S = 30


def changed(root: Path, globs: list[str]) -> list[str]:
    out = set()
    for cmd in (["git", "diff", "--name-only", "HEAD", "--"], ["git", "ls-files", "--others", "--exclude-standard", "--"]):
        r = subprocess.run([*cmd, *globs], cwd=root, capture_output=True, text=True, encoding="utf-8")
        out.update(ln for ln in r.stdout.splitlines() if ln)
    return sorted(f for f in out if (root / f).is_file())


def verify(root: Path) -> str | None:
    lint = harness_config.load(root).get("lint") or {}
    if not lint.get("command"):
        return None
    files = changed(root, lint.get("globs") or ["*"])
    if not files:
        return None
    name = " ".join(lint["command"])
    try:
        r = subprocess.run(
            [*lint["command"], *files],
            cwd=root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=TIMEOUT_S,
        )
    except subprocess.TimeoutExpired:
        return f"stop-verify: {name} {TIMEOUT_S}초 초과 — 건너뜀"
    except OSError as e:
        return f"stop-verify: {name} 를 실행할 수 없음({e}) — 검사 건너뜀(린트 실패 아님)"
    if r.returncode == 0:
        return f"stop-verify: {name} 통과 ({len(files)}개 파일)"
    tail = "\n".join((r.stdout + r.stderr).strip().splitlines()[-20:])
    return f"stop-verify: {name} 실패 — {tail}"


def main() -> None:
    with contextlib.suppress(Exception, SystemExit):  # 훅은 세션을 막지 않는다(harness.json 없음 포함)
        sys.stdin.read()
        root = Path(os.environ.get("CLAUDE_PROJECT_DIR") or harness_config.ROOT)
        msg = verify(root)
        if msg:
            print(json.dumps({"systemMessage": msg}, ensure_ascii=False))


if __name__ == "__main__":
    main()
    sys.exit(0)
