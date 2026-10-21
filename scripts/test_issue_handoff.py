"""issue_handoff 훅: 깨지면 엉뚱한 이슈에 코멘트가 달리거나, 매 응답마다 코멘트가 쏟아진다.

실행: uv run pytest scripts/test_issue_handoff.py
"""

import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "issue_handoff", Path(__file__).parent / "hooks" / "issue_handoff.py"
)
h = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(h)


def test_issue_from_branch_then_file(tmp_path):
    assert h.issue_number("chore/152-status-briefing", tmp_path) == "152"
    assert h.issue_number("docs/2026-10-15-x", tmp_path) is None  # 날짜를 이슈로 오판하지 않음
    (tmp_path / ".claude").mkdir()
    (tmp_path / ".claude" / "current-issue").write_text("#77\n", encoding="utf-8")
    assert h.issue_number("wip", tmp_path) == "77"
    assert h.issue_number("main", tmp_path) is None  # main 에선 파일 폴백 끔
    assert h.issue_number("feat/9-x", tmp_path) == "9"  # 브랜치가 먼저


def test_no_duplicate_within_60_minutes_or_same_head(tmp_path):
    stamp = tmp_path / "stamp"
    assert h.should_post(stamp, "152", "sha1", now=1000)
    h.mark_posted(stamp, "152", "sha1", now=1000)
    assert not h.should_post(stamp, "152", "sha2", now=1000 + 3599)  # 60분 안
    assert h.should_post(stamp, "152", "sha2", now=1000 + 3600)
    assert not h.should_post(stamp, "152", "sha1", now=1000 + 99999)  # HEAD 그대로
    assert h.should_post(stamp, "153", "sha1", now=1001)  # 다른 이슈는 별개


def test_gh_failure_is_not_shown_as_no_pr(tmp_path):
    def fake_sh(cmd, root, stdin=None):
        if cmd[0] == "gh":
            return None, "HTTP 401: Bad credentials"
        return "", ""

    body = h.build_body(tmp_path, "chore/152-x", sh=fake_sh)
    assert "조회 실패" in body
    assert "PR 만들기" not in body and "PR 없음" not in body
