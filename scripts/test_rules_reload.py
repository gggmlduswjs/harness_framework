"""rules_reload 훅 회귀 테스트.

깨지면: compaction 뒤 규칙이 컨텍스트로 돌아오지 않거나, rules/ 가 없는 레포에서 세션 시작이 깨진다.
실행: uv run --no-project --with pytest python -m pytest scripts/test_rules_reload.py -q
"""

import os
import subprocess
import sys
from pathlib import Path

HOOK = Path(__file__).resolve().parent.parent / ".claude" / "hooks" / "rules_reload.py"


def _run(project: Path) -> subprocess.CompletedProcess:
    env = {**os.environ, "CLAUDE_PROJECT_DIR": str(project)}
    return subprocess.run(
        [sys.executable, "-I", str(HOOK)], capture_output=True, text=True, encoding="utf-8", env=env
    )


def test_missing_rules_is_silent(tmp_path):
    r = _run(tmp_path)
    assert r.returncode == 0
    assert r.stdout == ""


def test_prints_principles_and_index(tmp_path):
    rules = tmp_path / "rules"
    rules.mkdir()
    (rules / "principles.md").write_text("# 원칙\n의존성 방향 마커", encoding="utf-8")
    (rules / "INDEX.yaml").write_text("version: 1\nproject: demo-marker\n", encoding="utf-8")
    r = _run(tmp_path)
    assert r.returncode == 0
    assert "의존성 방향 마커" in r.stdout
    assert "demo-marker" in r.stdout
