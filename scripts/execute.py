#!/usr/bin/env python3
"""
Harness Step Executor — phase 내 step을 순차 실행하고 자가 교정한다.

Usage:
    python scripts/execute.py <phase-dir> [--push] [--engine claude|codex]

--engine codex: Codex CLI 는 Claude Code 훅(block-dangerous·tdd-guard·audit-log)을 거치지 않는다.
위험 명령 차단·TDD 강제·감사 기록이 없고, 남는 방어선은 프롬프트 맨 앞 금지 목록(FORBIDDEN)뿐이다.
step 출력은 JSONL 전체 대신 마지막 agent_message 와 usage 만 stdout 에 저장한다.

원본: bigsix scripts/execute.py (이 레포 옛 execute.py 의 진화판).
레포마다 다른 값(가드레일 문서·근거 패턴·슬롯 폴더)은 harness.json.
가드레일 문서 = harness.json guardrail_docs 중 있는 것만, 읽기·쓰기 utf-8 고정(Windows cp949),
프롬프트는 stdin 으로 넘긴다(가드레일이 Windows 명령줄 길이 32K 를 넘는다).
메인 체크아웃에서는 돌지 않는다(worktree 강제), step 프롬프트 맨 앞에 금지 목록,
커밋은 `git add -A` 대신 바뀐 파일만 이름으로 add(.env*·audit.jsonl 등 제외).
근거 강제: index.json 에 issue 번호가 없거나 step md 에 근거 docs 경로가 없으면 실행하지 않는다.
"""

import argparse
import contextlib
import fnmatch
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
import types
from datetime import datetime, timedelta, timezone
from pathlib import Path

import baden_tasks
import harness_config
import slot

ROOT = harness_config.ROOT
_CFG = harness_config.load()
WORKTREE_BASE = slot.WORKTREE_BASE

# step 실행 엔진. 둘 다 권한 확인 없이 돈다 — 그래서 FORBIDDEN 을 프롬프트 맨 앞에 붙인다.
ENGINES = {
    "claude": ["claude", "-p", "--dangerously-skip-permissions", "--output-format", "json"],
    # Windows npm 설치는 codex.cmd 라 which 로 찾는다(CreateProcess 는 .exe 만 붙인다).
    "codex": [
        shutil.which("codex") or "codex",
        "exec",
        "--dangerously-bypass-approvals-and-sandbox",
        "--json",
        "-",
    ],
}
ENGINE_TIMEOUT_S = 1800
# Claude Code 훅(.claude/settings.json)은 claude 엔진에만 걸린다.
NO_HOOKS_WARN = (
    "  WARN: 엔진 {engine}: Claude Code 훅(block-dangerous·tdd-guard·audit-log)을 거치지 않는다 "
    "— 위험 명령 차단·TDD 강제·감사 기록 없음, 금지 목록 프롬프트만 남는다"
)


TAIL_CHARS = 4096


def _compact_codex(stdout: str, exit_code: int = 0) -> str:
    """codex --json JSONL 에서 마지막 agent_message·usage(turn.completed)·실패 이벤트 줄만 남긴다.

    원문 전체를 저장하면 step 하나에 1MB 넘게 커밋된다(step 11개면 ~7MB).
    실패 원인이 사라지지 않게 turn.failed·error 줄은 모두 남기고, 비정상 종료·남은 줄 없음·
    JSON 아닌 줄이 있으면 원문 끝 약 4KB 를 붙인다.
    """
    last_msg = usage = None
    failures: list[str] = []
    broken = False
    for line in stdout.splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except ValueError:
            broken = True
            continue
        if not isinstance(event, dict):
            broken = True
            continue
        if event.get("type") in ("turn.failed", "error"):
            failures.append(line)
            continue
        item = event.get("item")
        if (
            event.get("type") == "item.completed"
            and isinstance(item, dict)
            and item.get("type") == "agent_message"
        ):
            last_msg = line
        elif event.get("type") == "turn.completed":
            usage = line
    kept = [x for x in (*failures, last_msg, usage) if x]
    if exit_code != 0 or not kept or broken:
        kept += ["[harness] raw tail:", stdout[-TAIL_CHARS:]]
    return "\n".join(kept)


def _kill_tree(proc: subprocess.Popen) -> None:
    if sys.platform == "win32":  # 엔진 자식까지(트리) 끈다
        subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)], capture_output=True)
    else:  # start_new_session 으로 만든 그룹 전체
        os.killpg(proc.pid, signal.SIGKILL)
    proc.wait()


def _run_engine(
    cmd: list[str], prompt: str, cwd: str, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess:
    """엔진을 돌리고 끝나면 바로 돌아온다.

    출력은 파이프가 아니라 임시 파일로 받는다. 파이프면 엔진이 띄운 Gradle 데몬처럼
    출력을 물려받은 손자 프로세스가 살아 있는 동안 EOF 가 안 와서 하네스가 멈춘다
    (실측 31분 멈춤). 시간 초과는 예외 대신 실패 결과로 돌려 재시도 흐름을 탄다.
    """
    with (
        tempfile.TemporaryFile("w+", encoding="utf-8") as fin,
        tempfile.TemporaryFile("w+", encoding="utf-8") as fout,
        tempfile.TemporaryFile("w+", encoding="utf-8") as ferr,
    ):
        fin.write(prompt)
        fin.seek(0)
        proc = subprocess.Popen(
            cmd,
            stdin=fin,
            stdout=fout,
            stderr=ferr,
            cwd=cwd,
            env=env,
            start_new_session=sys.platform != "win32",
        )
        try:
            code = proc.wait(timeout=ENGINE_TIMEOUT_S)
            note = ""
        except subprocess.TimeoutExpired:
            _kill_tree(proc)
            code, note = -1, f"\n[harness] timeout after {ENGINE_TIMEOUT_S}s — engine killed"
        except BaseException:
            # Ctrl+C 등으로 빠질 때도 엔진을 먼저 끈다 — 슬롯 잠금이 풀린 뒤 엔진이 계속 쓰지 않게.
            # ponytail: 하네스 PID 만 밖에서 강제 종료하면 엔진이 남는다.
            # 막으려면 Windows Job Object.
            _kill_tree(proc)
            raise
        fout.seek(0)
        ferr.seek(0)
        return subprocess.CompletedProcess(cmd, code, fout.read(), ferr.read() + note)


# 매 step 프롬프트 맨 앞에 붙는다. claude -p 를 --dangerously-skip-permissions 로 부르기 때문.
FORBIDDEN = (
    "## ⛔ 금지 목록 (어기면 step 실패로 처리한다)\n\n"
    "- 운영 DB 쓰기 금지 (운영 DB 호스트 접속 포함)\n"
    "- 마이그레이션 적용 금지 (운영·공유 DB 에 alembic upgrade·flyway migrate·"
    "gradlew flywayMigrate 금지 — 파일 작성만)\n"
    "- 머지 금지 (git merge·gh pr merge)\n"
    "- push 금지 (git push — 사람이 한다)\n"
    "- `git add -A` / `git add .` 금지 — 고친 파일만 이름으로 add\n"
    "- .env 파일 읽기 금지 (.env·.env.* — 비밀값이 프롬프트·로그로 샌다)\n\n"
    "---\n\n"
)

# 커밋에 넣지 않는 경로 패턴(경로 조각마다 fnmatch).
# 비밀 .env 만 뺀다 — .env.example·apps/web/.env.mock 같은 커밋된 파일은 add 돼야 한다.
STAGE_EXCLUDE = (
    ".env",
    ".env.local",
    ".env.*.local",
    "audit.jsonl",
    "__pycache__",
    "node_modules",
    ".gradle",
    "*.log",
)


def worktree_error(cwd: str | Path) -> str | None:
    """cwd 가 메인 체크아웃이 아닌 git worktree 면 None, 아니면 거절 사유."""

    def git(*args: str) -> str | None:
        r = subprocess.run(
            ["git", *args], cwd=str(cwd), capture_output=True, text=True, encoding="utf-8"
        )
        return r.stdout.strip() if r.returncode == 0 else None

    git_dir = git("rev-parse", "--absolute-git-dir")
    common = git("rev-parse", "--path-format=absolute", "--git-common-dir")
    hint = (
        "  고정 슬롯을 준비한 뒤 그 폴더에서 실행하라(잠금은 execute.py 가 건다):\n"
        "  uv run python scripts/slot.py open <제품>-<레이어>\n"
        f"  실행 폴더: {Path(WORKTREE_BASE) / '<제품>-<레이어>'}"
    )
    if git_dir is None or common is None:
        return f"ERROR: git 저장소가 아닙니다 ({cwd}).\n{hint}"
    if Path(git_dir).resolve() == Path(common).resolve():
        return (
            "ERROR: 메인 체크아웃에서는 execute.py 를 돌리지 않는다 — step 세션이 권한 확인 없이 "
            f"커밋한다 ({cwd}).\n{hint}"
        )
    return None


EVIDENCE = re.compile(rf"(?<![\w-])({_CFG['evidence']['pattern']})")
# 가드레일 말고도 근거로 치지 않는 공통 문서 — 진행 순서·셋업 절차는 기능 스펙이 아니다
NOT_EVIDENCE = tuple(_CFG["evidence"].get("not_evidence", ()))


def evidence_error(phase_dir: Path, guardrail_docs: tuple[str, ...]) -> str | None:
    """phase 근거 검사: index.json 에 issue 번호, 각 step md 에 근거 문서 경로가 있어야 한다.

    근거 = EVIDENCE(harness.json evidence.pattern)에 맞는 경로 중 가드레일로 이미 주입되는 문서와
    NOT_EVIDENCE 를 뺀 것(제품 spec·화면 명세·도메인 규칙·ADR).
    레포에 실제로 있는 파일만 친다(지어낸 경로 거부).
    """
    idx = json.loads((phase_dir / "index.json").read_text(encoding="utf-8"))
    issue = idx.get("issue")
    if not isinstance(issue, int) or isinstance(issue, bool) or issue <= 0:
        return (
            f"ERROR: {phase_dir.name}/index.json 에 이슈 번호가 없다 — "
            "이슈 없이 phase 를 돌리지 않는다.\n"
            '  "issue": <GitHub 이슈 번호> 를 넣어라(gh issue create 로 먼저 만든다).'
        )
    if not idx.get("steps"):  # 빈 phase 를 돌리면 할 일 없이 completed 로 찍힌다
        return f"ERROR: {phase_dir.name}/index.json 의 steps 가 비었다 — /harness 로 먼저 채워라."
    missing = []
    for s in idx.get("steps", []):
        f = phase_dir / f"step{s['step']}.md"
        refs = EVIDENCE.findall(f.read_text(encoding="utf-8")) if f.is_file() else []
        root = phase_dir.parent.parent
        if not [
            r
            for r in refs
            if r not in guardrail_docs and r not in NOT_EVIDENCE and (root / r).is_file()
        ]:
            missing.append(f.name)
    if missing:
        return (
            f"ERROR: 근거 문서가 없는 step: {', '.join(missing)}\n"
            "  「읽어야 할 파일」에 관련 docs/ 스펙(제품 spec·화면 명세·ADR 중 하나 이상) "
            "경로를 적어라 (.claude/commands/harness.md D-3)."
        )
    return None


def changed_paths(porcelain_z: str) -> list[str]:
    """`git status --porcelain -z -uall` 출력 → 바뀐 경로(제외 패턴 뺀 것)."""
    out: list[str] = []
    parts = porcelain_z.split("\0")
    i = 0
    while i < len(parts):
        entry = parts[i]
        i += 1
        if len(entry) < 4:
            continue
        xy, path = entry[:2], entry[3:]
        if "R" in xy or "C" in xy:
            i += 1  # -z 형식: 이름 바뀜은 다음 칸이 옛 경로
        segs = path.replace("\\", "/").split("/")
        if any(fnmatch.fnmatch(seg, pat) for seg in segs for pat in STAGE_EXCLUDE):
            continue
        out.append(path)
    return out


@contextlib.contextmanager
def progress_indicator(label: str):
    """터미널 진행 표시기. with 문으로 사용하며 .elapsed 로 경과 시간을 읽는다."""
    frames = "◐◓◑◒"
    stop = threading.Event()
    t0 = time.monotonic()

    def _animate():
        idx = 0
        while not stop.wait(0.12):
            sec = int(time.monotonic() - t0)
            sys.stderr.write(f"\r{frames[idx % len(frames)]} {label} [{sec}s]")
            sys.stderr.flush()
            idx += 1
        sys.stderr.write("\r" + " " * (len(label) + 20) + "\r")
        sys.stderr.flush()

    th = threading.Thread(target=_animate, daemon=True)
    th.start()
    info = types.SimpleNamespace(elapsed=0.0)
    try:
        yield info
    finally:
        stop.set()
        th.join()
        info.elapsed = time.monotonic() - t0


class StepExecutor:
    """Phase 디렉토리 안의 step들을 순차 실행하는 하네스."""

    MAX_RETRIES = 3
    FEAT_MSG = "feat({phase}): step {num} — {name}"
    CHORE_MSG = "chore({phase}): step {num} output"
    TZ = timezone(timedelta(hours=9))
    GUARDRAIL_DOCS = tuple(_CFG["guardrail_docs"])

    def __init__(self, phase_dir_name: str, *, auto_push: bool = False, engine: str = "claude"):
        self._root = str(ROOT)
        self._phases_dir = ROOT / "phases"
        self._phase_dir = self._phases_dir / phase_dir_name
        self._phase_dir_name = phase_dir_name
        self._top_index_file = self._phases_dir / "index.json"
        self._auto_push = auto_push
        self._engine = engine
        # 재실행해도 같은 값 — step 세션의 Baden 보고가 phase 단위로 묶인다
        self._task_id = f"harness-{phase_dir_name}"

        if not self._phase_dir.is_dir():
            print(f"ERROR: {self._phase_dir} not found")
            sys.exit(1)

        self._index_file = self._phase_dir / "index.json"
        if not self._index_file.exists():
            print(f"ERROR: {self._index_file} not found")
            sys.exit(1)

        idx = self._read_json(self._index_file)
        self._project = idx.get("project", "project")
        self._phase_name = idx.get("phase", phase_dir_name)
        self._total = len(idx["steps"])

    def run(self):
        err = worktree_error(self._root)
        if err:
            print(err)
            sys.exit(1)
        err = evidence_error(self._phase_dir, self.GUARDRAIL_DOCS)
        if err:
            print(err)
            sys.exit(1)
        root = Path(self._root).resolve()
        base = Path(WORKTREE_BASE).resolve()
        slot_name = None
        if root.parent == base:
            try:
                slot.parse_slot(root.name)
            except ValueError:
                pass
            else:
                slot_name = root.name
        pid = os.getpid()
        if slot_name is None:
            print("WARN: 슬롯 밖 worktree — 고정 슬롯(<제품>-<레이어>) 사용 권장")
        else:
            try:
                slot.acquire(
                    slot_name,
                    issue=self._read_json(self._index_file)["issue"],
                    phase=self._phase_name,
                    pid=pid,
                    repo=root,
                    base=base,
                )
            except (OSError, RuntimeError, ValueError) as error:
                print(f"ERROR: {error}")
                sys.exit(1)
        # 이 실행 중 커밋에 Baden-Task 트레일러(prepare-commit-msg)
        with contextlib.suppress(Exception):
            baden_tasks.add(self._task_id, self._root)
        try:
            self._print_header()
            self._check_blockers()
            self._checkout_branch()
            guardrails = self._load_guardrails()
            self._ensure_created_at()
            self._execute_all_steps(guardrails)
            self._finalize()
        finally:
            with contextlib.suppress(Exception):
                baden_tasks.remove(self._task_id, self._root)
            if slot_name is not None:
                slot.release(slot_name, pid=pid, base=base)

    # --- timestamps ---

    def _stamp(self) -> str:
        return datetime.now(self.TZ).strftime("%Y-%m-%dT%H:%M:%S%z")

    # --- JSON I/O ---

    @staticmethod
    def _read_json(p: Path) -> dict:
        return json.loads(p.read_text(encoding="utf-8"))

    @staticmethod
    def _write_json(p: Path, data: dict):
        p.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    # --- git ---

    def _run_git(self, *args) -> subprocess.CompletedProcess:
        cmd = ["git", *args]
        return subprocess.run(cmd, cwd=self._root, capture_output=True, text=True, encoding="utf-8")

    def _checkout_branch(self):
        branch = f"feat-{self._phase_name}"

        r = self._run_git("rev-parse", "--abbrev-ref", "HEAD")
        if r.returncode != 0:
            print("  ERROR: git을 사용할 수 없거나 git repo가 아닙니다.")
            print(f"  {r.stderr.strip()}")
            sys.exit(1)

        if r.stdout.strip() == branch:
            return

        r = self._run_git("rev-parse", "--verify", branch)
        if r.returncode == 0:
            r = self._run_git("checkout", branch)
        else:
            r = self._run_git("fetch", "origin")
            if r.returncode != 0:
                print("  ERROR: git fetch origin 실패.")
                print(f"  {r.stderr.strip()}")
                sys.exit(1)
            r = self._run_git("checkout", "-b", branch, "origin/main")

        if r.returncode != 0:
            print(f"  ERROR: 브랜치 '{branch}' checkout 실패.")
            print(f"  {r.stderr.strip()}")
            print("  Hint: 변경사항을 stash하거나 commit한 후 다시 시도하세요.")
            sys.exit(1)

        print(f"  Branch: {branch}")

    def _stage_changes(self, *skip: str) -> None:
        """바뀐 파일만 이름으로 add 한다(`git add -A` 금지 규칙)."""
        r = self._run_git("status", "--porcelain", "-z", "-uall")
        paths = [p for p in changed_paths(r.stdout) if p not in skip]
        if paths:
            self._run_git("add", "--", *paths)

    def _commit_step(self, step_num: int, step_name: str):
        output_rel = f"phases/{self._phase_dir_name}/step{step_num}-output.json"
        index_rel = f"phases/{self._phase_dir_name}/index.json"
        self._stage_changes(output_rel, index_rel)  # 상태 파일은 chore 커밋으로

        if self._run_git("diff", "--cached", "--quiet").returncode != 0:
            msg = self.FEAT_MSG.format(phase=self._phase_name, num=step_num, name=step_name)
            r = self._run_git("commit", "-m", msg)
            if r.returncode == 0:
                print(f"  Commit: {msg}")
            else:
                print(f"  WARN: 코드 커밋 실패: {r.stderr.strip()}")

        self._stage_changes()
        if self._run_git("diff", "--cached", "--quiet").returncode != 0:
            msg = self.CHORE_MSG.format(phase=self._phase_name, num=step_num)
            r = self._run_git("commit", "-m", msg)
            if r.returncode != 0:
                print(f"  WARN: housekeeping 커밋 실패: {r.stderr.strip()}")

    # --- top-level index ---

    def _update_top_index(self, status: str):
        if not self._top_index_file.exists():
            return
        top = self._read_json(self._top_index_file)
        ts = self._stamp()
        for phase in top.get("phases", []):
            if phase.get("dir") == self._phase_dir_name:
                phase["status"] = status
                ts_key = {
                    "completed": "completed_at",
                    "error": "failed_at",
                    "blocked": "blocked_at",
                }.get(status)
                if ts_key:
                    phase[ts_key] = ts
                break
        self._write_json(self._top_index_file, top)

    # --- guardrails & context ---

    def _load_guardrails(self) -> str:
        """있는 문서만 넣는다: harness.json guardrail_docs.

        나머지 문서는 step 파일의 「읽어야 할 파일」로 세션이 직접 읽는다.
        """
        sections = []
        for rel in self.GUARDRAIL_DOCS:
            doc = Path(self._root) / rel
            if doc.is_file():
                sections.append(f"## {rel}\n\n{doc.read_text(encoding='utf-8')}")
        return "\n\n---\n\n".join(sections) if sections else ""

    @staticmethod
    def _build_step_context(index: dict) -> str:
        lines = [
            f"- Step {s['step']} ({s['name']}): {s['summary']}"
            for s in index["steps"]
            if s["status"] == "completed" and s.get("summary")
        ]
        if not lines:
            return ""
        return "## 이전 Step 산출물\n\n" + "\n".join(lines) + "\n\n"

    def _build_preamble(
        self, guardrails: str, step_context: str, prev_error: str | None = None
    ) -> str:
        commit_example = self.FEAT_MSG.format(phase=self._phase_name, num="N", name="<step-name>")
        retry_section = ""
        if prev_error:
            retry_section = (
                f"\n## ⚠ 이전 시도 실패 — 아래 에러를 반드시 참고하여 수정하라\n\n"
                f"{prev_error}\n\n---\n\n"
            )
        return (
            f"{FORBIDDEN}"
            f"당신은 {self._project} 프로젝트의 개발자입니다. 아래 step을 수행하세요.\n\n"
            f"{guardrails}\n\n---\n\n"
            f"{step_context}{retry_section}"
            f"## 작업 규칙\n\n"
            f"1. 이전 step에서 작성된 코드를 확인하고 일관성을 유지하라.\n"
            f"2. 이 step에 명시된 작업만 수행하라. 추가 기능이나 파일을 만들지 마라.\n"
            f"3. 기존 테스트를 깨뜨리지 마라.\n"
            f"4. AC(Acceptance Criteria) 검증을 직접 실행하라.\n"
            f"5. /phases/{self._phase_dir_name}/index.json의 해당 step status를 업데이트하라:\n"
            f'   - AC 통과 → "completed" + "summary" 필드에 이 step의 산출물을 한 줄로 요약\n'
            f'   - {self.MAX_RETRIES}회 수정 시도 후에도 실패 → "error" + "error_message" 기록\n'
            f"   - 사용자 개입이 필요한 경우 (API 키, 인증, 수동 설정 등) → "
            f'"blocked" + "blocked_reason" 기록 후 즉시 중단\n'
            f"6. 모든 변경사항을 커밋하라:\n"
            f"   {commit_example}\n\n---\n\n"
        )

    # --- Claude 호출 ---

    def _invoke_claude(self, step: dict, preamble: str) -> dict:
        step_num, step_name = step["step"], step["name"]
        step_file = self._phase_dir / f"step{step_num}.md"

        if not step_file.exists():
            print(f"  ERROR: {step_file} not found")
            sys.exit(1)

        prompt = preamble + step_file.read_text(encoding="utf-8")
        # step 세션이 Baden 에 같은 taskId 로 보고한다(서버가 꺼져 있으면 무시된다)
        env = {**os.environ, "BADEN_TASK_ID": self._task_id}
        result = _run_engine(ENGINES[self._engine], prompt, self._root, env)

        if result.returncode != 0:
            print(f"\n  WARN: Claude가 비정상 종료됨 (code {result.returncode})")
            if result.stderr:
                print(f"  stderr: {result.stderr[:500]}")

        output = {
            "step": step_num,
            "name": step_name,
            "exitCode": result.returncode,
            "stdout": _compact_codex(result.stdout, result.returncode)
            if self._engine == "codex"
            else result.stdout,
            "stderr": result.stderr,
        }
        out_path = self._phase_dir / f"step{step_num}-output.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2, ensure_ascii=False)

        return output

    # --- 헤더 & 검증 ---

    def _print_header(self):
        print(f"\n{'=' * 60}")
        print("  Harness Step Executor")
        print(f"  Phase: {self._phase_name} | Steps: {self._total}")
        if self._auto_push:
            print("  Auto-push: enabled")
        if self._engine != "claude":
            print(NO_HOOKS_WARN.format(engine=self._engine))
        print(f"{'=' * 60}")

    def _check_blockers(self):
        index = self._read_json(self._index_file)
        for s in reversed(index["steps"]):
            if s["status"] == "error":
                print(f"\n  ✗ Step {s['step']} ({s['name']}) failed.")
                print(f"  Error: {s.get('error_message', 'unknown')}")
                print("  Fix and reset status to 'pending' to retry.")
                sys.exit(1)
            if s["status"] == "blocked":
                print(f"\n  ⏸ Step {s['step']} ({s['name']}) blocked.")
                print(f"  Reason: {s.get('blocked_reason', 'unknown')}")
                print("  Resolve and reset status to 'pending' to retry.")
                sys.exit(2)
            if s["status"] != "pending":
                break

    def _ensure_created_at(self):
        index = self._read_json(self._index_file)
        if "created_at" not in index:
            index["created_at"] = self._stamp()
            self._write_json(self._index_file, index)

    # --- 실행 루프 ---

    def _execute_single_step(self, step: dict, guardrails: str) -> bool:
        """단일 step 실행 (재시도 포함). 완료되면 True, 실패/차단이면 False."""
        step_num, step_name = step["step"], step["name"]
        done = sum(
            1 for s in self._read_json(self._index_file)["steps"] if s["status"] == "completed"
        )
        prev_error = None

        for attempt in range(1, self.MAX_RETRIES + 1):
            index = self._read_json(self._index_file)
            step_context = self._build_step_context(index)
            preamble = self._build_preamble(guardrails, step_context, prev_error)

            tag = f"Step {step_num}/{self._total - 1} ({done} done): {step_name}"
            if attempt > 1:
                tag += f" [retry {attempt}/{self.MAX_RETRIES}]"

            with progress_indicator(tag) as pi:
                self._invoke_claude(step, preamble)
                elapsed = int(pi.elapsed)

            index = self._read_json(self._index_file)
            status = next(
                (s.get("status", "pending") for s in index["steps"] if s["step"] == step_num),
                "pending",
            )
            ts = self._stamp()

            if status == "completed":
                for s in index["steps"]:
                    if s["step"] == step_num:
                        s["completed_at"] = ts
                self._write_json(self._index_file, index)
                self._commit_step(step_num, step_name)
                print(f"  ✓ Step {step_num}: {step_name} [{elapsed}s]")
                return True

            if status == "blocked":
                for s in index["steps"]:
                    if s["step"] == step_num:
                        s["blocked_at"] = ts
                self._write_json(self._index_file, index)
                reason = next(
                    (s.get("blocked_reason", "") for s in index["steps"] if s["step"] == step_num),
                    "",
                )
                print(f"  ⏸ Step {step_num}: {step_name} blocked [{elapsed}s]")
                print(f"    Reason: {reason}")
                self._update_top_index("blocked")
                sys.exit(2)

            err_msg = next(
                (
                    s.get("error_message", "Step did not update status")
                    for s in index["steps"]
                    if s["step"] == step_num
                ),
                "Step did not update status",
            )

            if attempt < self.MAX_RETRIES:
                for s in index["steps"]:
                    if s["step"] == step_num:
                        s["status"] = "pending"
                        s.pop("error_message", None)
                self._write_json(self._index_file, index)
                prev_error = err_msg
                print(f"  ↻ Step {step_num}: retry {attempt}/{self.MAX_RETRIES} — {err_msg}")
            else:
                for s in index["steps"]:
                    if s["step"] == step_num:
                        s["status"] = "error"
                        s["error_message"] = f"[{self.MAX_RETRIES}회 시도 후 실패] {err_msg}"
                        s["failed_at"] = ts
                self._write_json(self._index_file, index)
                self._commit_step(step_num, step_name)
                print(
                    f"  ✗ Step {step_num}: {step_name} failed after "
                    f"{self.MAX_RETRIES} attempts [{elapsed}s]"
                )
                print(f"    Error: {err_msg}")
                self._update_top_index("error")
                sys.exit(1)

        return False  # unreachable

    def _execute_all_steps(self, guardrails: str):
        while True:
            index = self._read_json(self._index_file)
            pending = next((s for s in index["steps"] if s["status"] == "pending"), None)
            if pending is None:
                print("\n  All steps completed!")
                return

            step_num = pending["step"]
            for s in index["steps"]:
                if s["step"] == step_num and "started_at" not in s:
                    s["started_at"] = self._stamp()
                    self._write_json(self._index_file, index)
                    break

            self._execute_single_step(pending, guardrails)

    def _finalize(self):
        index = self._read_json(self._index_file)
        index["completed_at"] = self._stamp()
        self._write_json(self._index_file, index)
        self._update_top_index("completed")

        self._stage_changes()
        if self._run_git("diff", "--cached", "--quiet").returncode != 0:
            msg = f"chore({self._phase_name}): mark phase completed"
            r = self._run_git("commit", "-m", msg)
            if r.returncode == 0:
                print(f"  ✓ {msg}")

        if self._auto_push:
            branch = f"feat-{self._phase_name}"
            r = self._run_git("push", "-u", "origin", branch)
            if r.returncode != 0:
                print(f"\n  ERROR: git push 실패: {r.stderr.strip()}")
                sys.exit(1)
            print(f"  ✓ Pushed to origin/{branch}")

        print(f"\n{'=' * 60}")
        print(f"  Phase '{self._phase_name}' completed!")
        print(f"{'=' * 60}")


def main():
    parser = argparse.ArgumentParser(description="Harness Step Executor")
    parser.add_argument("phase_dir", help="Phase directory name (e.g. 0-mvp)")
    parser.add_argument("--push", action="store_true", help="Push branch after completion")
    parser.add_argument(
        "--engine",
        choices=sorted(ENGINES),
        default="claude",
        help="실행 엔진 (codex 는 Claude Code 훅을 거치지 않는다)",
    )
    args = parser.parse_args()

    StepExecutor(args.phase_dir, auto_push=args.push, engine=args.engine).run()


if __name__ == "__main__":
    main()
