"""TDD Guard — PreToolUse[Edit|Write]. harness.json 「tdd_guard」 가 켜졌을 때만 동작한다.

돈·규칙이 걸린 파일(tdd_guard.targets 글롭, 레포 루트 기준)을 그에 맞는 테스트
(tdd_guard.tests 템플릿 — {parent}=상위 폴더 이름, {mod}=확장자 뺀 파일 이름) 없이 고치려 하면 막는다.
나머지(웹·문서·설정·마이그레이션)는 통과 — CLAUDE.md 「중요한 것만」.
입력이 깨져 경로를 못 읽으면 통과시키지 않는다(fail-closed). 막을 때도 exit 0 + deny JSON.
원본: bigsix scripts/hooks/tdd-guard.sh (설정을 읽으려고 python 으로 옮겼다)
"""

import fnmatch
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import harness_config


def deny(reason: str) -> None:
    out = {"hookEventName": "PreToolUse", "permissionDecision": "deny"}
    # ASCII JSON escapes preserve the reason even on non-UTF-8 Windows stdout.
    print(json.dumps({"hookSpecificOutput": {**out, "permissionDecisionReason": reason}}))


def check(file_path: str, root: Path, cfg: dict) -> str | None:
    """막을 사유, 통과면 None."""
    if not cfg.get("enabled"):
        return None
    if not file_path:
        return "TDD GUARD: 입력에서 file_path 를 읽지 못했습니다."
    try:
        rel = Path(file_path).resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return None  # 레포 밖 파일
    name = rel.rsplit("/", 1)[-1]
    if name.startswith("test_") or name.endswith("_test.py"):
        return None
    if not any(fnmatch.fnmatch(rel, pat) for pat in cfg.get("targets", [])):
        return None
    p = Path(rel)
    parent, mod = p.parent.name, p.stem
    tests = [t.format(parent=parent, mod=mod) for t in cfg.get("tests", [])]
    if any(any(root.glob(t)) for t in tests):
        return None
    want = tests[0] if tests else f"tests/test_{mod}.py"
    return (
        f"TDD GUARD: {rel} 에 걸린 테스트가 없습니다. 다음 할 일: {want} 에 실패하는 테스트를 "
        "먼저 쓰고(빨간불 확인) 그 다음 구현을 고치세요."
    )


def main() -> None:
    try:
        file_path = (json.load(sys.stdin).get("tool_input") or {}).get("file_path") or ""
    except ValueError:
        file_path = ""
    root = Path(os.environ.get("CLAUDE_PROJECT_DIR") or harness_config.ROOT)
    try:
        cfg = harness_config.load(root).get("tdd_guard") or {}
    except SystemExit:
        cfg = {}  # harness.json 이 없으면 꺼진 것으로 본다 — 그 파일을 만드는 편집까지 막지 않게
    reason = check(file_path, root, cfg)
    if reason:
        deny(reason)


if __name__ == "__main__":
    main()
