"""status.py 핵심: 깨지면 진행 상태가 틀리게 보인다.

- 문서에 손 상태 표기가 다시 생기거나 없는 PR 번호가 있으면 경고가 떠야 한다(일부러 틀린 fixture).
- gh 실패는 「조회 실패」로 보여야 한다(0건으로 숨기면 안 된다).
- phases step 집계.
실행: uv run pytest scripts/test_status.py
"""

import importlib.util
import json
from pathlib import Path

_spec = importlib.util.spec_from_file_location("status", Path(__file__).parent / "status.py")
status = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(status)

PRS = [
    {"number": 10, "state": "MERGED", "headRefName": "feat/done"},
    {"number": 11, "state": "OPEN", "headRefName": "feat/wip"},
]


def test_hand_marks_and_unknown_prs_are_flagged():
    doc = "\n".join(
        [
            "| 1-1 | 로그인 | PR #10 |",  # 맞음
            "| 1-2 | ✅ | PR #11 |",  # 틀림: 손 상태 표기
            "| 1-3 | 세트 | PR #99 |",  # 틀림: 없는 PR
        ]
    )
    found = status.find_mismatches(doc, PRS, "x.md")
    assert len(found) == 2
    assert found[0].startswith("x.md:2") and "손 상태 표기" in found[0]
    assert found[1].startswith("x.md:3 PR #99")


def test_gh_failure_shows_lookup_failed(tmp_path):
    data = {
        "generated_at": "t",
        "phases": [],
        "prs": {"error": "auth"},
        "open_prs": {"error": "auth"},
        "issues": {"error": "auth"},
        "warnings": [],
    }
    out = status.render(data)
    assert out.count("조회 실패") == 3
    assert "0건" not in out


def test_phase_counts(tmp_path):
    d = tmp_path / "phases" / "web-1-demo"
    d.mkdir(parents=True)
    steps = [{"status": "completed"}, {"status": "completed"}, {"status": "blocked"}]
    (d / "index.json").write_text(json.dumps({"steps": steps}), encoding="utf-8")
    [row] = status.load_phases(tmp_path)
    assert (row["product"], row["total"], row["completed"], row["blocked"]) == ("web", 3, 2, 1)
