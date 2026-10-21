#!/usr/bin/env python3
"""Additive harness bundle adoption. Preview by default; never replace project files."""
import argparse
import json
import re
import stat
import sys
from pathlib import Path

import harness_config

PACKAGE = Path(__file__).resolve().parent.parent


def safe_path(root: Path, relative: Path) -> Path:
    path = root / relative
    for part in (path, *path.parents):
        if part == root:
            break
        try:
            metadata = part.lstat()
        except FileNotFoundError:
            continue
        # st_file_attributes predates Path.is_junction (Python 3.12).
        reparse = getattr(metadata, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT
        if stat.S_ISLNK(metadata.st_mode) or reparse:
            raise ValueError(f"linked destination refused: {part}")
    if not path.resolve().is_relative_to(root):
        raise ValueError(f"destination outside project: {path}")
    return path


def bundle() -> dict[Path, bytes]:
    files = {}
    for name in ("harness.json", "CLAUDE.md", "AGENTS.md", ".gitignore"):
        files[Path(name)] = (PACKAGE / name).read_bytes()
    for folder in ("scripts", "rules", "templates"):
        for p in (PACKAGE / folder).rglob("*"):
            if p.is_file() and not any(x in p.parts for x in ("__pycache__", ".pytest_cache")):
                if folder == "scripts" and p.suffix != ".py" and p.name != "prepare-commit-msg":
                    continue
                if folder != "scripts" and p.suffix not in (".md", ".yaml"):
                    continue
                files[p.relative_to(PACKAGE)] = p.read_bytes()
    for name in ("settings.json", "hooks/block_dangerous.py", "hooks/rules_reload.py",
                 "commands/harness.md", "commands/review.md", "agents/rule-guard.md",
                 "skills/briefing/SKILL.md"):
        relative = Path(".claude") / name
        files[relative] = (PACKAGE / relative).read_bytes()
    for p in (PACKAGE / "templates/project").rglob("*"):
        if p.is_file():
            files[p.relative_to(PACKAGE / "templates/project")] = p.read_bytes()
    for name in ("WORKFLOW.md", "SAFETY.md"):
        files[Path("docs") / name] = (PACKAGE / "docs" / name).read_bytes()
    return files


def write_missing(root: Path, files: dict[Path, bytes], apply: bool) -> None:
    # Preflight all destinations before creating any directory or file.
    paths = [(safe_path(root, rel), content) for rel, content in files.items()]
    for path, _ in paths:
        if path.exists() and not path.is_file():
            raise ValueError(f"file destination is a directory: {path}")
        for parent in path.parents:
            if parent.exists() and not parent.is_dir():
                raise ValueError(f"parent is not a directory: {parent}")
    for path, content in paths:
        if path.exists():
            same = path.read_bytes() == content
            print(f"KEEP {'same' if same else 'different (manual review)'} {path.relative_to(root)}")
            continue
        print(f"ADD {path.relative_to(root)}")
        if apply:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("xb") as stream:
                stream.write(content)
            if path.relative_to(root) == Path("scripts/githooks/prepare-commit-msg"):
                path.chmod(path.stat().st_mode | 0o111)


def feature(root: Path, slug: str, issue: int, apply: bool) -> None:
    if not re.fullmatch(r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*", slug) or len(slug) > 64:
        raise ValueError("feature name must be a lowercase portable slug (max 64)")
    if slug in {"con", "prn", "aux", "nul", *(f"com{i}" for i in range(1, 10)),
                *(f"lpt{i}" for i in range(1, 10))}:
        raise ValueError("feature name is reserved on Windows")
    if issue <= 0:
        raise ValueError("issue must be positive")
    feature_dir = safe_path(root, Path("docs/specs") / slug)
    phase_dir = safe_path(root, Path("phases") / slug)
    if feature_dir.exists() or phase_dir.exists():
        raise ValueError("feature already exists; choose a new slug or edit it manually")
    index_path = safe_path(root, Path("phases/index.json"))
    index = json.loads(index_path.read_text(encoding="utf-8")) if index_path.exists() else {"phases": []}
    if not isinstance(index, dict) or not isinstance(index.get("phases"), list):
        raise TypeError("phases/index.json must contain a phases list")
    if any(not isinstance(p, dict) or not isinstance(p.get("dir"), str) for p in index["phases"]):
        raise ValueError("invalid phase entry")
    if any(p["dir"] == slug for p in index["phases"]):
        raise ValueError("phase already indexed")
    files = {}
    for p in (PACKAGE / "templates/feature").glob("*.md"):
        content = p.read_text(encoding="utf-8").replace("{{feature}}", slug)
        content = content.replace("{{issue}}", str(issue))
        files[Path("docs/specs") / slug / p.name] = content.encode("utf-8")
    config_path = safe_path(root, Path("harness.json"))
    config = harness_config.load(root) if config_path.exists() else {}
    if not isinstance(config, dict):
        raise TypeError("harness.json must contain an object")
    phase = {"project": config.get("project", "my-project"), "phase": slug, "issue": issue,
             "steps": [{"step": 0, "name": slug, "status": "pending"}]}
    files[Path("phases") / slug / "index.json"] = json_bytes(phase)
    files[Path("phases") / slug / "step0.md"] = (
        "# Step 0: " + slug + "\n\n"
        "## 읽어야 할 파일\n\n"
        f"- docs/specs/{slug}/SPEC.md\n- docs/specs/{slug}/PLAN.md\n"
        f"- docs/specs/{slug}/TASKS.md\n- docs/WORKFLOW.md\n\n"
        "## 작업\n\nDRAFT: SPEC/PLAN/TASKS의 미정 항목을 먼저 구체화한다. "
        "미정 상태면 구현하지 말고 blocked_reason을 기록한다. "
        "TASK-001만 구현하고 허용 경로와 AC 검증 명령을 따른다.\n\n"
        "## Acceptance Criteria\n\nTASKS.md의 TASK-001 검증 명령과 수동 QA를 실행한다. "
        "실행하지 못한 검증은 통과로 기록하지 않는다.\n\n"
        "## 완료 보고\n\nVERIFICATION.md에 AC별 결과, 실제 명령과 종료 코드, "
        "변경 파일, 남은 위험을 남긴다. 성공 시 해당 step을 completed + summary, "
        "실패 시 error + error_message, 외부 개입 필요 시 blocked + blocked_reason으로 기록한다.\n"
    ).encode("utf-8")
    # Validate the index destination and every new file before any write.
    for rel in files:
        safe_path(root, rel)
    temp = safe_path(root, Path("phases/index.json.harness-tmp"))
    if temp.exists():
        raise ValueError("stale phases/index.json.harness-tmp; inspect it before retrying")
    write_missing(root, files, apply)
    index["phases"].append({"dir": slug, "status": "pending"})
    print("UPDATE phases/index.json")
    if apply:
        # Only this shared index is updated; its unrelated fields/entries are retained.
        created = False
        try:
            with temp.open("xb") as stream:
                created = True
                stream.write(json_bytes(index))
            temp.replace(index_path)
        finally:
            if created and temp.exists():
                temp.unlink()


def json_bytes(data: dict) -> bytes:
    return (json.dumps(data, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    for action in ("init", "feature"):
        p = sub.add_parser(action)
        p.add_argument("target", type=Path)
        p.add_argument("--apply", action="store_true", help="write changes; default is preview")
        if action == "feature":
            p.add_argument("slug")
            p.add_argument("--issue", type=int, required=True)
    args = parser.parse_args()
    root = args.target.resolve()
    try:
        if args.action == "init":
            write_missing(root, bundle(), args.apply)
        else:
            feature(root, args.slug, args.issue, args.apply)
        print("Applied." if args.apply else "Preview only. Add --apply to write.")
        return 0
    except (OSError, ValueError, TypeError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
