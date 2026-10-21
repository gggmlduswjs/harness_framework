# 프로젝트: {프로젝트명}

## 어디를 보나
- [docs/PRD.md](docs/PRD.md) — 무엇을·왜
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — 구조·데이터 흐름
- [docs/ADR.md](docs/ADR.md) — 기술 결정
- [docs/UI_GUIDE.md](docs/UI_GUIDE.md) — UI 규칙

## 기술 스택
- {프레임워크 (예: Next.js 15)}
- {언어 (예: TypeScript strict mode)}
- {스타일링 (예: Tailwind CSS)}

## 아키텍처 규칙
- CRITICAL: {절대 지켜야 할 규칙 1 (예: 모든 API 로직은 app/api/ 라우트 핸들러에서만 처리)}
- CRITICAL: {절대 지켜야 할 규칙 2 (예: 클라이언트 컴포넌트에서 직접 외부 API를 호출하지 말 것)}
- {일반 규칙 (예: 컴포넌트는 components/ 폴더에, 타입은 types/ 폴더에 분리)}

## 개발 프로세스
- CRITICAL: 새 기능 구현 시 반드시 테스트를 먼저 작성하고, 테스트가 통과하는 구현을 작성할 것 (TDD)
- 큰 작업은 `/harness`로 step 분해 → `scripts/execute.py` 순차 실행.
- 커밋 메시지는 conventional commits 형식을 따를 것 (feat:, fix:, docs:, refactor:)

## 규칙 체계 (`rules/`)
```
rules/
  INDEX.yaml          ← 트리거 레지스트리 (paths/patterns/imports/events)
  principles.md       ← Tier 1 원칙 ≤6, 항상 로드
  concerns/C*.md      ← Tier 2 횡단 관심사
  specifics/S-*.md    ← Tier 3 도메인 규칙
  _analysis.md / _audit-vN.md ← 분석·감사 기록 (규칙 아님)
```
- **로딩:** `principles.md` 는 항상. 파일을 읽거나 편집할 때 `INDEX.yaml` trigger 가 맞으면 해당 concern/specific 을 추가로 읽는다.
- MUST / MUST NOT 을 침범하게 되면 수정 제안 **전에** 규칙 ID 를 밝혀 경고한다. PREFER / Exception 은 판단 맥락으로만.
- **compaction 후:** `principles.md`·`INDEX.yaml` 을 다시 읽는다(SessionStart `compact` 훅 `.claude/hooks/rules_reload.py` 가 출력). 본문은 trigger 로 재판단.
- **`rule-guard` 호출:** 명시 요청 시 · 여러 파일을 편집한 뒤 · PR 전. 판정만 하고 고치지 않는다.
- 코드로 판정 가능한 것 = `rules/`, 판정 불가능한 작업 방식 = `tasks/*-protocol.md`. 둘이 어긋나면 프로토콜이 배치 기록을 이긴다.
- 새 레포에 규칙 세우기: `rules/README.md`.

## 명령어
- {개발 서버·빌드·테스트 명령 (예: `npm run dev`, `uv run pytest tests/<고친 곳>`)}
- 린트는 Stop 훅이 바뀐 파일만 돌린다 — 명령은 `harness.json` `lint`.
- 하네스: `uv run python scripts/slot.py open <제품>-<레이어>` → 그 슬롯에서 `python scripts/execute.py <phase>` · 상태 `uv run python scripts/status.py` · 하네스 테스트 `uv run --no-project --with pytest python -m pytest scripts/ -q`

## 하네스 설정 (`harness.json` — 레포마다 다른 값은 여기만 고친다)
- `project` — 프로젝트 이름(Baden Project Name 으로도 쓴다)
- `worktree_base` — 슬롯 worktree 폴더. 상대 경로는 메인 체크아웃 기준
- `slots` — `products`·`layers`·`extra`(슬롯 이름 = `<product>-<layer>` 또는 extra, 접미 `-2..-9`), `max_live`(살아 있는 슬롯 상한), `max_live_server`(`server` 레이어 상한)
- `guardrail_docs` — execute.py 가 매 step 프롬프트에 넣는 문서(있는 것만)
- `evidence` — step md 근거 문서 정규식 `pattern`, 근거로 안 치는 `not_evidence`
- `status` — `check_docs`(손 상태 표기·없는 PR 검사 대상), `group_labels`(이슈 묶음), `flag_labels`(이슈 옆 표시)
- `lint` — Stop 훅: 바뀐 파일 중 `globs` 에 맞는 것만 `command` 뒤에 붙여 실행(30초, 막지 않음)
- `tdd_guard` — `enabled`(기본 false), `targets`(테스트 없이 못 고치는 파일 글롭, 루트 기준), `tests`(통과 조건 글롭 — `{parent}` 상위 폴더, `{mod}` 파일 이름)

## Baden Monitoring (선택 — 안 쓰면 이 절을 지운다)
- Project Name: `harness.json` 의 `project`.
- 새 지시를 받으면 작업 시작 전에 `baden_start_task`(prompt, projectName) → 받은 taskId 를 이후 모든 보고에 쓴다.
- 방향·계획을 정하면 `baden_plan`. 읽기·검색·수정·테스트 실행 전에 `baden_action`, 검증은 `baden_verify`. 끝나면 `baden_complete_task`.
- baden 서버가 꺼져 있어도 보고는 조용히 버려지고 작업은 막히지 않는다 — 재시도하지 않는다.
- 커밋 트레일러 `Baden-Task: <taskId>` 는 자동이다 — `baden_start_task`/`complete_task` 의 PostToolUse 훅이 `<git-dir>/baden-tasks`(worktree 별)에 넣고 빼고, `scripts/githooks/prepare-commit-msg` 가 붙인다. 손으로 쓰지 않는다.
- git 훅 설치: SessionStart 가 `core.hooksPath` 비어 있으면 `scripts/githooks` 로 둔다. 다른 값이면 경고만 — 그 훅에서 `scripts/baden_tasks.py commit-msg "$1"` 을 불러라.
- 서브에이전트(rule-guard 등)는 MCP 를 못 쓴다 → `scripts/baden_report.py` 로 HTTP 보고한다. 메인 세션은 MCP 도구 그대로.

## 상속 (계층)
- 전역 습관·취향은 `~/.claude/CLAUDE.md`(모든 프로젝트)에서 상속 → 충돌 시 이 파일(프로젝트 규칙)이 우선.
- 폴더 특수 규칙은 각 폴더에 `CLAUDE.md`를 두면 그 폴더 작업 시 자동 로드됨. 이 파일에 다 몰아넣지 말 것.
