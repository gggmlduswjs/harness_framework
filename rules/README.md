# rules/ — 새 레포에 규칙 세우기

코드를 보고 위반을 판정하는 프로젝트 규칙. 로딩 규약은 루트 `CLAUDE.md` 「규칙 체계」, 감사는 `rule-guard` 서브에이전트.

## 3계층

| Tier | 파일 | 언제 로드 |
| --- | --- | --- |
| 1 Principles | `principles.md` (≤6개) | 항상 |
| 2 Concerns | `concerns/C*.md` | `INDEX.yaml` trigger 매치 시 |
| 3 Specifics | `specifics/S-*.md` | `INDEX.yaml` trigger 매치 시 |

## 부트스트랩 순서

1. **분석** — 구조·공통 패턴·안티패턴·정적 분석 현황을 `rules/_analysis.md` 에 적는다.
2. **설계** — Tier 를 정하고 `INDEX.yaml` trigger 를 잡는다. `project`·`baden.projectName` = `harness.json` `project`.
3. **작성** — principles → concerns → specifics. 레포가 이미 따르는 좋은 패턴을 격상한다.
4. **감사** — 전체 코드를 배치로 나눠 대조하고 결과를 `rules/_audit-v1.md` 에 남긴다(개정마다 `_audit-vN.md`).

자세한 절차(원본 프롬프트):
- 부트스트랩: https://github.com/ibare/baden/blob/main/prompts/baden-rules-bootstrap-guide-claude.ko.md
- 개정: https://github.com/ibare/baden/blob/main/prompts/rules-revision-prompt.ko.md

## 쓰는 원칙

- **린터·타입체커가 잡는 건 규칙에 넣지 않는다.** 규칙은 의미·맥락 판단만.
- **강제할 수 없는 조항은 두지 않는다.** 판정 기준이 없으면 PREFER 로 내리거나 지운다.
- **반복 위반은 검사 스크립트로 내린다** → `rule-guard` 는 의미 판단만 한다.
- 고칠 때 frontmatter `version` 을 올리고, 코드와 다시 대조했으면 `last_verified` 를 갱신한다.
- 판정 불가능한 작업 방식(무엇을 만들지, 배치를 어떻게 돌릴지)은 `tasks/*-protocol.md` 로 뺀다.
