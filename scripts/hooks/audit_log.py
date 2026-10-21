"""Audit Log — PostToolUse(모든 도구). 절대 막지 않는다.

.claude/audit.jsonl 에 {ts, tool, args(200자·비밀 가림), ok} 한 줄을 붙인다.
원본: bigsix scripts/hooks/audit_log.py
"""

import contextlib
import json
import os
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

SECRET = re.compile(
    r"(?i:authorization\s*:\s*(?:bearer|basic|token)\s+)\S+"  # 헤더 값 본체
    r"|(?i:\b(?:bearer|basic)\s+)[\w.~+/=-]{8,}"
    r"|\b[A-Za-z0-9_]*(?i:key|secret|token|password|passwd)[A-Za-z0-9_]*[\"']?\s*[=:]\s*"
    r"(?:'[^']*'|\"[^\"]*\"|\S+)"  # SERVICE_ACCESS_KEY=… · api_key: … · JSON "password":"x"
    r"|(?:-u|--user)\s+\S+:\S+"  # curl -u user:pass
    r"|AKIA[0-9A-Z]{16}"  # AWS 액세스 키
    r"|sk-[A-Za-z0-9_-]{8,}|gh[pousr]_[A-Za-z0-9]{8,}|eyJ[\w-]+\.[\w-]+\.[\w-]+"
    r"|postgres(?:ql)?://[^\s'\"]+"
)


def redact(text: str) -> str:
    return SECRET.sub("[REDACTED]", text)


def main() -> None:
    d = json.load(sys.stdin)
    ti = d.get("tool_input") or {}
    args = ti.get("command") or ti.get("file_path") or ti.get("pattern")
    args = redact(str(args or json.dumps(ti, ensure_ascii=False)))[:200]
    resp = d.get("tool_response")
    ok = not (
        isinstance(resp, dict)
        and (resp.get("is_error") or resp.get("error") or resp.get("interrupted"))
    )
    root = Path(os.environ.get("CLAUDE_PROJECT_DIR") or d.get("cwd") or ".")
    rec = {
        "ts": datetime.now(UTC).isoformat(timespec="seconds"),
        "tool": d.get("tool_name", ""),
        "args": args,
        "ok": ok,
    }
    with open(root / ".claude" / "audit.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    with contextlib.suppress(Exception):  # 감사 로그 실패로 도구를 막지 않는다
        main()
