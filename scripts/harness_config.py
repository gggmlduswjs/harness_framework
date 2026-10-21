"""harness.json 읽기 — 레포마다 다른 값(경로·제품·라벨·문서·린트)은 전부 그 파일 하나에 둔다."""

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load(root: Path = ROOT) -> dict:
    path = root / "harness.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise SystemExit(
            f"ERROR: {path} 가 없다 — 레포 루트에 harness.json 을 두고 값을 채워라(CLAUDE.md 「하네스 설정」)."
        ) from None


def main_checkout(root: Path = ROOT) -> Path:
    """worktree 안에서도 메인 체크아웃 경로. git 이 안 되면 root."""
    r = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "--path-format=absolute", "--git-common-dir"],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return Path(r.stdout.strip()).parent if r.returncode == 0 and r.stdout.strip() else root


def resolve(path: str, root: Path = ROOT) -> Path:
    """상대 경로는 메인 체크아웃 기준 — 슬롯 worktree 에서 돌아도 같은 곳을 가리킨다."""
    p = Path(path)
    return p if p.is_absolute() else (main_checkout(root) / p).resolve()
