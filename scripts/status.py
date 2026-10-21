"""진행 상태를 계산해서 보여 준다 — 손으로 쓰는 ✅🔄⬜ 대신 이 출력이 상태다.

입력: phases/*/index.json(step 상태) + GitHub(gh CLI: PR·CI·리뷰·이슈).
gh 가 실패하면 그 칸은 「조회 실패」로 보인다(0·빈칸으로 숨기지 않는다 — 미측정≠0).

    uv run python scripts/status.py            # 마크다운 상태표
    uv run python scripts/status.py --json     # 같은 내용 JSON
    uv run python scripts/status.py --check    # harness.json status.check_docs 에 손 상태 표기·
                                               # 없는 PR 번호가 있으면 경고 + exit 1

gh 토큰이 필요해서 CI 에서는 돌리지 않는다. 로컬·/briefing 에서 돌린다.
문서·라벨은 harness.json 「status」. 원본: bigsix scripts/status.py
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import harness_config

ROOT = harness_config.ROOT
_CFG = harness_config.load()["status"]
CHECK_DOCS = tuple(_CFG["check_docs"])
FAIL = "조회 실패"
GROUP_LABELS = tuple(_CFG["group_labels"])  # 열린 이슈를 이 라벨로 묶는다
FLAG_LABELS = tuple(_CFG["flag_labels"])  # 이슈 옆에 [표시]
ISSUE_BRANCH = re.compile(r"^[a-z]+/(\d+)-")


def gh(*args: str):
    """gh 를 JSON 으로 부른다. 실패하면 (None, 사유)."""
    try:
        r = subprocess.run(
            ["gh", *args], capture_output=True, text=True, encoding="utf-8", timeout=60, cwd=ROOT
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        return None, str(e)
    if r.returncode != 0:
        return None, (r.stderr or r.stdout).strip()[:200]
    try:
        return json.loads(r.stdout or "null"), None
    except ValueError as e:
        return None, f"JSON 해석 실패: {e}"


def load_phases(root: Path = ROOT) -> list[dict]:
    rows = []
    for index in sorted((root / "phases").glob("*/index.json")):
        try:
            steps = json.loads(index.read_text(encoding="utf-8")).get("steps", [])
        except (OSError, ValueError) as e:
            rows.append({"dir": index.parent.name, "error": f"{FAIL}: {e}"})
            continue
        count = defaultdict(int)
        for s in steps:
            count[s.get("status", "pending")] += 1
        name = index.parent.name
        rows.append(
            {"dir": name, "product": name.split("-")[0], "total": len(steps), **dict(count)}
        )
    return rows


def ci_summary(rollup: list | None) -> str:
    """CI 결과 한 칸. rollup 이 없으면(None) 「조회 실패」, 모르는 결론은 「판정 불가」."""
    if rollup is None:
        return FAIL
    if not rollup:
        return "CI 없음"
    bad, pending, unknown = [], 0, []
    for c in rollup:
        result = (c.get("conclusion") or c.get("state") or "").upper()
        if result in ("FAILURE", "ERROR", "CANCELLED", "TIMED_OUT", "ACTION_REQUIRED"):
            bad.append(c.get("name") or c.get("context") or "?")
        elif result in ("SUCCESS", "NEUTRAL", "SKIPPED"):
            continue
        elif result in ("", "PENDING", "EXPECTED") and (c.get("status") or "") != "COMPLETED":
            pending += 1
        else:
            unknown.append(result or "결론 없음")
    if bad:
        return "실패(" + ", ".join(bad) + ")"
    if unknown:
        return "판정 불가: " + ", ".join(unknown)
    return "진행 중" if pending else "통과"


def collect(root: Path = ROOT) -> dict:
    data: dict = {"generated_at": datetime.now(UTC).isoformat(timespec="seconds")}
    data["phases"] = load_phases(root)
    fields = "number,title,state,headRefName,mergedAt,closingIssuesReferences"
    prs, err = gh("pr", "list", "--state", "all", "--limit", "300", "--json", fields)
    data["prs"] = prs if err is None else {"error": err}
    open_prs, err = gh(
        "pr",
        "list",
        "--state",
        "open",
        "--json",
        "number,title,headRefName,isDraft,reviewDecision,statusCheckRollup,closingIssuesReferences",
    )
    if err is None:
        for p in open_prs:
            p["ci"] = ci_summary(p.pop("statusCheckRollup", None))
    data["open_prs"] = open_prs if err is None else {"error": err}
    issues, err = gh(
        "issue", "list", "--state", "open", "--limit", "200", "--json", "number,title,labels"
    )
    if err is None:
        for i in issues:
            i["labels"] = [lb["name"] for lb in i["labels"]]
    data["issues"] = issues if err is None else {"error": err}
    data["warnings"] = warnings(data, local_branches(root))
    return data


def local_branches(root: Path = ROOT) -> list[str]:
    r = subprocess.run(
        ["git", "worktree", "list", "--porcelain"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=root,
    )
    return [ln.split("refs/heads/", 1)[1] for ln in r.stdout.splitlines() if "refs/heads/" in ln]


def warnings(data: dict, branches: list[str]) -> list[str]:
    """같은 이슈를 두 줄기가 잡음 · 결정 대기 · blocked."""
    out = []
    by_issue: dict[str, set] = defaultdict(set)
    open_prs = data["open_prs"] if isinstance(data["open_prs"], list) else []
    for b in branches + [p["headRefName"] for p in open_prs]:
        if m := ISSUE_BRANCH.match(b):
            by_issue[m.group(1)].add(b)
    for n, bs in sorted(by_issue.items()):
        if len(bs) > 1:
            out.append(f"이슈 #{n} 을 두 줄기가 잡고 있다: {', '.join(sorted(bs))}")
    if isinstance(data["issues"], list):
        for label, msg in (("decision", "결정 대기"), ("blocked", "막힘")):
            for i in data["issues"]:
                if label in i["labels"]:
                    out.append(f"{msg}: #{i['number']} {i['title']}")
    return out


def render(data: dict) -> str:
    L = [f"# 진행 상태 (계산값 · {data['generated_at']}) — 손으로 고치지 않는다", ""]
    L += ["## 단계 (phases/)", ""]
    if not data["phases"]:
        L.append("phases/ 에 phase 없음 — `/harness` 로 만든 단계가 아직 없다.")
    else:
        L += ["| 제품 | phase | 완료/전체 | error | blocked |", "|---|---|---|---|---|"]
        for p in data["phases"]:
            if "error" in p:
                L.append(f"| ? | {p['dir']} | {p['error']} | | |")
                continue
            L.append(
                f"| {p['product']} | {p['dir']} | {p.get('completed', 0)}/{p['total']}"
                f" | {p.get('error', 0)} | {p.get('blocked', 0)} |"
            )
    L += ["", "## 열린 PR (머지 대기)", ""]
    op = data["open_prs"]
    if isinstance(op, dict):
        L.append(f"{FAIL}: {op['error']}")
    elif not op:
        L.append("열린 PR 0건")
    else:
        L += ["| PR | 제목 | 브랜치 | CI | 리뷰 | Closes |", "|---|---|---|---|---|---|"]
        for p in op:
            closes = " ".join(f"#{i['number']}" for i in p.get("closingIssuesReferences") or [])
            review = p.get("reviewDecision") or "리뷰 없음"
            draft = " (초안)" if p.get("isDraft") else ""
            L.append(
                f"| #{p['number']}{draft} | {p['title']} | `{p['headRefName']}` | {p['ci']}"
                f" | {review} | {closes or '-'} |"
            )
    L += ["", "## 최근 7일 머지", ""]
    prs = data["prs"]
    if isinstance(prs, dict):
        L.append(f"{FAIL}: {prs['error']}")
    else:
        since = (datetime.now(UTC) - timedelta(days=7)).isoformat()
        merged = sorted(
            (p for p in prs if p.get("mergedAt") and p["mergedAt"] >= since),
            key=lambda p: p["mergedAt"],
            reverse=True,
        )
        L += [f"- #{p['number']} {p['title']} ({p['mergedAt'][:10]})" for p in merged[:10]]
        L.append(f"(합계 {len(merged)}건{', 최근 10건만 보임' if len(merged) > 10 else ''})")
    L += ["", "## 열린 이슈", ""]
    issues = data["issues"]
    if isinstance(issues, dict):
        L.append(f"{FAIL}: {issues['error']}")
    else:
        groups = defaultdict(list)
        for i in issues:
            key = next((lb for lb in GROUP_LABELS if lb in i["labels"]), "기타")
            groups[key].append(i)
        for key in (*GROUP_LABELS, "기타"):
            if groups[key]:
                L.append(f"**{key}**")
                for i in groups[key]:
                    flags = [lb for lb in FLAG_LABELS if lb in i["labels"]]
                    tag = f" [{', '.join(flags)}]" if flags else ""
                    L.append(f"- #{i['number']} {i['title']}{tag}")
        L.append(f"(합계 {len(issues)}건)")
    L += ["", "## 경고", ""]
    L += [f"- {w}" for w in data["warnings"]] or ["없음"]
    return "\n".join(L)


# --- 불일치 검사 -----------------------------------------------------------

HAND_MARK = re.compile(r"[✅🔄⬜]")
PR_REF = re.compile(r"PR\s*#(\d+)")


def find_mismatches(text: str, prs: list[dict], source: str = "") -> list[str]:
    """문서 대조: 손 상태 표기(✅🔄⬜)가 다시 생기면 경고, 적힌 PR 번호가 GitHub 에 없으면 경고.

    상태는 status.py 가 계산하므로 문서에는 순서·합격선·근거(PR 번호)만 둔다(2026-10-15).
    """
    known = {p["number"] for p in prs}
    out = []
    for lineno, line in enumerate(text.splitlines(), 1):
        where = f"{source}:{lineno}"
        if HAND_MARK.search(line):
            out.append(f"{where} 손 상태 표기 — status.py 가 계산한다, 지울 것")
        for m in PR_REF.finditer(line):
            if int(m.group(1)) not in known:
                out.append(f"{where} PR #{m.group(1)} — GitHub 에 없는 PR")
    return out


def check(root: Path = ROOT) -> int:
    prs, err = gh(
        "pr", "list", "--state", "all", "--limit", "500", "--json", "number,state,headRefName"
    )
    if err is not None:
        print(f"{FAIL} — 불일치 검사를 못 했다: {err}")
        return 2
    found = []
    for rel in CHECK_DOCS:
        path = root / rel
        if path.exists():
            found += find_mismatches(path.read_text(encoding="utf-8"), prs, rel)
    for f in found:
        print(f"경고: {f}")
    print(f"불일치 {len(found)}건 ({', '.join(CHECK_DOCS)} 대 GitHub PR {len(prs)}건)")
    return 1 if found else 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--json", action="store_true", help="JSON 으로 출력")
    ap.add_argument("--check", action="store_true", help="문서 표기와 GitHub 상태 불일치 검사")
    a = ap.parse_args(argv)
    if a.check:
        return check()
    data = collect()
    print(json.dumps(data, ensure_ascii=False, indent=2) if a.json else render(data))
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
