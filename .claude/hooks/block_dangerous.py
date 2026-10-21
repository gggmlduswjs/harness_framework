"""PreToolUse 훅: 위험한 셸 명령·.env 읽기를 막는다. 입력은 stdin JSON, exit 2 = 차단.

Bash|PowerShell: command 를 본다. Read: file_path 가 비밀 .env 면 막는다.
.env.example·.sample·.mock·.template 은 비밀이 아니라 허용.
원본: bigsix .claude/hooks/block_dangerous.py
안전띠지 보안 경계가 아니다: 정규식이라 우회 표현(python 으로 열기 등)은 못 막고,
깨진 입력은 exit 2로 막는다(fail-closed).
"""

import json
import re
import shlex
import sys
from pathlib import PurePath

DANGEROUS = re.compile(
    r"\brm\s+(-\w*r\w*f\w*|-\w*f\w*r\w*)\b"  # rm -rf · -fr · -Rf · -rfv
    r"|\brm\s+(-\w+\s+)*(-r|-R|--recursive)\s+(-\w+\s+)*(-f|--force)\b"  # rm -r -f
    r"|\brm\s+(-\w+\s+)*(-f|--force)\s+(-\w+\s+)*(-r|-R|--recursive)\b"  # rm -f -r
    r"|Remove-Item\b[^|;&]*-Recurse[^|;&]*-Force|Remove-Item\b[^|;&]*-Force[^|;&]*-Recurse"
    r"|\bgit\s+push\b[^|;&]*\s(--force\b|--force-with-lease\b|-\w*f\w*\b|\+\S)"  # -uf · +refspec
    r"|\bgit\s+reset\s+--hard"
    r"|\bDROP\s+(TABLE|SCHEMA|DATABASE)\b"
    r"|\bpsql\b[^|;&]*(supabase\.co|pooler\.supabase\.com|\bprod\b)",  # 운영 DB 직접 접속
    re.IGNORECASE,
)
# 내용을 출력하는 명령. grep·rg·sed·awk 는 첫 위치 인자가 검색어·스크립트라
# 그것만 빼고 파일 자리를 본다.
READ_CMDS = {"cat", "type", "less", "more", "head", "tail", "bat", "source", "get-content", "gc"}
PATTERN_FIRST = {"grep", "egrep", "fgrep", "rg", "sed", "awk", "select-string"}
SEARCH_CMDS = {"grep", "egrep", "fgrep", "rg", "select-string"}
SEGMENT = re.compile(r"[|;&]+")
# 커밋·PR 문구는 실행되지 않는 글이다 — 판정 전에 걷어 낸다.
MESSAGE_ARG = re.compile(
    r"(?:\s)(?:-m|-F|--message|--body|--body-file|--title)(?:\s+|=)"
    r"(\"(?:[^\"\\]|\\.)*\"|'[^']*'|\S+)"
)
QUOTED = re.compile(r"\"(?:[^\"\\]|\\.)*\"|'[^']*'")


def is_secret_env(path: str) -> bool:
    name = PurePath(path.strip("'\"").replace("\\", "/")).name
    return bool(re.fullmatch(r"\.env(\.[\w.-]+)?", name, re.IGNORECASE)) and not re.search(
        r"\.(example|sample|mock|template)$", name, re.IGNORECASE
    )


def _tokens(segment: str) -> list[str]:
    try:
        return shlex.split(segment, posix=False)  # posix=False: Windows 경로의 \ 를 살린다
    except ValueError:
        return segment.split()


def _command_at(toks: list[str]) -> tuple[str, list[str]]:
    """세그먼트에서 읽기·검색 명령 이름과 그 뒤 인자. `git grep` 도 grep 으로 본다."""
    for i, t in enumerate(toks):
        name = t.strip("'\"").lower()
        if name in READ_CMDS or name in PATTERN_FIRST:
            return name, toks[i + 1 :]
    return "", []


def reads_env(command: str) -> bool:
    for seg in SEGMENT.split(command):
        name, rest = _command_at(_tokens(seg))
        if not name:
            continue
        pos = [t for t in rest if not t.startswith("-")]
        explicit = any(t in ("-e", "-f", "--regexp", "--file", "-Pattern") for t in rest)
        if name in PATTERN_FIRST and pos and not explicit:
            pos = pos[1:]  # 검색어·스크립트 자리
        if any(is_secret_env(t) for t in pos):
            return True
    return False


def strip_search_patterns(command: str) -> str:
    """grep·rg·git grep·Select-String 의 따옴표 인자(검색어)는 실행되지 않는다 — 걷어 낸다."""
    out = []
    for seg in re.split(r"([|;&]+)", command):
        name, _ = _command_at(_tokens(seg))
        out.append(QUOTED.sub(" ", seg) if name in SEARCH_CMDS else seg)
    return "".join(out)


def blocked(tool_input: dict) -> bool:
    command = MESSAGE_ARG.sub(" ", " " + (tool_input.get("command") or ""))
    file_path = tool_input.get("file_path") or ""
    return bool(DANGEROUS.search(strip_search_patterns(command)) or reads_env(command)) or (
        bool(file_path) and is_secret_env(file_path)
    )


if __name__ == "__main__":
    try:
        event = json.load(sys.stdin)
        if not isinstance(event, dict) or not isinstance(event.get("tool_input"), dict):
            raise TypeError("invalid tool_input")
        tool_input = event["tool_input"]
        for field in ("command", "file_path"):
            if field in tool_input and not isinstance(tool_input[field], str):
                raise ValueError("invalid field type")
        if not any(tool_input.get(field) for field in ("command", "file_path")):
            raise ValueError("missing command or file_path")
    except (ValueError, TypeError, OSError):
        print("BLOCKED: invalid safety-hook input", file=sys.stderr)
        sys.exit(2)
    if blocked(tool_input):
        what = tool_input.get("command") or tool_input.get("file_path")
        print(f"BLOCKED: 위험한 명령어가 감지되었습니다: {what}", file=sys.stderr)
        sys.exit(2)
