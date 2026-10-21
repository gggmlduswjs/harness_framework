---
name: briefing
description: 아침판(세션 시작)·저녁판(세션 끝) 한 장. 아침판 = status.py 상태 + 열린 이슈와 마지막 handoff + 머지 대기 PR(CI·리뷰) + 결정 대기 + 같은 이슈 두 세션 경고. 저녁판(`/briefing evening`) = 오늘 머지·한 일 / 못 한 일 / 하네스 개선 후보 3줄. 「브리핑」「오늘 뭐 해」「아침판」「저녁 정리」 요청에 쓴다.
---

# /briefing — 한 장 상태판

> 원본: bigsix .claude/skills/briefing/SKILL.md
> 상태는 손으로 쓰지 않는다. 숫자는 아래 명령 출력에서만 옮긴다. 명령이 실패하면 그 칸에 「조회 실패: 사유」를 적는다 — 0이나 빈칸으로 숨기지 않는다.
> 근거: `scripts/status.py` · Stop 훅 `scripts/hooks/issue_handoff.py`. 라벨·검사 문서는 `harness.json` 「status」.
> 읽기만 한다. 이슈·PR·문서를 고치지 않는다. 출력은 **한 장(40줄 안팎)**.

인자: 없음 = 아침판, `evening` = 저녁판.

## 아침판

1. 상태: `uv run python scripts/status.py --json` → 단계(phases)·열린 PR(CI·리뷰·Closes)·열린 이슈(라벨)·경고.
2. 불일치: `uv run python scripts/status.py --check` → 건수와 앞의 5건만. exit 2 면 「조회 실패」.
3. 이슈별 마지막 handoff — 열린 이슈마다:
   `gh issue view <N> --json comments --jq '[.comments[] | select(.body | startswith("<!-- issue-handoff -->"))] | last | .body'`
   없으면 「handoff 없음」. 있으면 「다음 할 일」 줄과 시각만 옮긴다.
4. 같은 이슈 두 세션: status 경고의 「두 줄기」 줄 + `in-progress` 라벨 이슈 중 열린 PR 이 2개 이상인 것.

출력 양식:

```
# 아침판 YYYY-MM-DD
## 지금 (status.py)
- 단계: … / 열린 PR n건 / 열린 이슈 n건 (group_labels 별 건수)
## 머지 대기 PR
| PR | 제목 | CI | 리뷰 | Closes |
## 결정 대기 (decision)
- #N 제목
## 이슈별 이어서 할 일 (마지막 handoff)
- #N 제목 — 다음 할 일 … (handoff 시각) / handoff 없음
## 경고
- 불일치 n건(앞 5건) · 두 세션 · blocked
## 오늘 추천
- … ← 이슈·PR 에서 고른다. 새 할 일을 지어내지 않는다
```

## 저녁판 (`/briefing evening`)

1. 오늘 머지: `gh pr list --state merged --search "merged:>=$(date +%F)" --json number,title`.
2. 오늘 한 일: `git log --since=midnight --oneline --all --no-merges` + 오늘 단 handoff 코멘트.
3. 못 한 일: 열린 PR 중 CI 실패·리뷰 대기, `in-progress` 이슈 중 오늘 커밋 없는 것, 아침판 추천 중 안 된 것.
4. 하네스 개선 후보: 오늘 같은 일을 손으로 3번 이상 했으면 그것(3번의 법칙). **3줄 이내.** 만들지는 않는다 — 사람 승인 뒤 이슈로.

출력 양식:

```
# 저녁판 YYYY-MM-DD
## 오늘 머지·한 일
## 못 한 일 (이유)
## 하네스 개선 후보 (≤3줄, 승인 전)
```
