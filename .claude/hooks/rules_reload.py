#!/usr/bin/env python3
"""SessionStart(compact) — compaction 뒤 rules/principles.md · rules/INDEX.yaml 을 다시 출력한다.

stdout 은 그대로 컨텍스트에 다시 들어간다. 규칙 본문(concerns/specifics)은 INDEX trigger 로 재판단한다.
파일이 없거나 읽을 수 없으면 아무것도 출력하지 않고 0 으로 끝낸다 — 세션을 막지 않는다.
"""

import contextlib
import os
import sys
from pathlib import Path

PATHS = ("rules/principles.md", "rules/INDEX.yaml")


def main() -> int:
    root = Path(os.environ.get("CLAUDE_PROJECT_DIR") or Path(__file__).resolve().parents[2])
    contents = []
    for rel in PATHS:
        with contextlib.suppress(OSError, UnicodeError):
            contents.append((rel, (root / rel).read_text(encoding="utf-8")))
    if not contents:
        return 0

    with contextlib.suppress(AttributeError, OSError):
        sys.stdout.reconfigure(encoding="utf-8")
    print("컨텍스트 compaction 발생 — 규칙을 다시 읽는다. 상세 규칙은 INDEX.yaml trigger 로 다시 고른다.")
    for rel, text in contents:
        print(f"\n## {rel}\n{text}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
