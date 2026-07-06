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

## 명령어
npm run dev      # 개발 서버
npm run build    # 프로덕션 빌드
npm run lint     # ESLint
npm run test     # 테스트

## 상속 (계층)
- 전역 습관·취향은 `~/.claude/CLAUDE.md`(모든 프로젝트)에서 상속 → 충돌 시 이 파일(프로젝트 규칙)이 우선.
- 폴더 특수 규칙은 각 폴더에 `CLAUDE.md`를 두면 그 폴더 작업 시 자동 로드됨. 이 파일에 다 몰아넣지 말 것.
