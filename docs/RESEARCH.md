# 강의 조사와 저장소 비교

조사일: 2026-10-21. Git으로 가져온 실제 커밋과 파일을 기준으로 조사했다.
GitHub 웹 캐시는 이보다 오래된 파일 목록을 보여서 비교 기준으로 사용하지 않았다.

| 자료 | 고정 커밋 |
|---|---|
| [강의 저장소](https://github.com/HyunjunJeon/fastcampus-harness-engineering-course/tree/c7090e63259ecb5d2bd84f2751cb44e0876becc2) | c7090e63259ecb5d2bd84f2751cb44e0876becc2 |
| [사용자 포크](https://github.com/gggmlduswjs/harness_framework/tree/473f5f229064b528bdae850f68ec4c02eed9a9ff) | 473f5f229064b528bdae850f68ec4c02eed9a9ff |
| [원본](https://github.com/jha0313/harness_framework/tree/da676bc689f10f6db38ff194cf25e983f59ac231) | da676bc689f10f6db38ff194cf25e983f59ac231 |

## Part 6 MVP (0→1)

직접 확인한 주요 자료:

- [2_reusable_templates.md](https://github.com/HyunjunJeon/fastcampus-harness-engineering-course/blob/c7090e63259ecb5d2bd84f2751cb44e0876becc2/part6_projects/mvp/2_reusable_templates.md):
  제품 요구·최소 범위·의존 순서·기능 계약·작업 범위·검증 결과를 재사용 가능한 문서로 나눈다.
- [3_ai_agent_mvp_process_kit.md](https://github.com/HyunjunJeon/fastcampus-harness-engineering-course/blob/c7090e63259ecb5d2bd84f2751cb44e0876becc2/part6_projects/mvp/3_ai_agent_mvp_process_kit.md):
  첫 사용자와 성공 경험을 좁힌 후 작업을 분해하고 증거를 리뷰하는 수강생용 진행 흐름이다.
- [zero_to_one_harness.md](https://github.com/HyunjunJeon/fastcampus-harness-engineering-course/blob/c7090e63259ecb5d2bd84f2751cb44e0876becc2/part6_projects/mvp/zero_to_one_harness.md):
  지침·역할·훅·반복 절차를 각각 분리하고 실행 범위와 결과 검증을 통제하는 설계다.
- [mvp_plan.md](https://github.com/HyunjunJeon/fastcampus-harness-engineering-course/blob/c7090e63259ecb5d2bd84f2751cb44e0876becc2/part6_projects/mvp/mvp_plan.md):
  Agent Control Plane 예제다. 목표·에이전트·이슈·실행·통제 기록의 제품 루프,
  상태 전이, 실패 행렬을 구체화한다. 해당 제품의 사업 로직은 공통 프레임워크에 넣지 않는다.
- [web_service_mvp_build_process.md](https://github.com/HyunjunJeon/fastcampus-harness-engineering-course/blob/c7090e63259ecb5d2bd84f2751cb44e0876becc2/part6_projects/mvp/web_service_mvp_build_process.md):
  화면 외에 실제 처리·저장·규칙·안전·운영까지 사용자가 확인하도록 한다.

채택: P0/P1/P2/제외, Golden Path, 상태·실패·복구, 작업 경로 제한, 실제 검증 증거.
변경: 강의의 번호식 문서명/최상위 specs/tasks 대신 기존 docs 근거 검사와 호환되는
`docs/PRD.md`, `docs/MVP_SCOPE.md`, `docs/ROADMAP.md`, `docs/specs/<feature>/`를 사용한다.
역할·엔진 분담과 병렬 실행은 고정하지 않는다. 특정 플러그인 설치를 실행 필수 조건으로 추가하지 않는다.
강의 본문·예제 코드의 대량 복사 대신 목적에 맞는 새 템플릿과 도입 코드를 작성했다.

## Part 6 production_project (1→10)

[project_setup.md](https://github.com/HyunjunJeon/fastcampus-harness-engineering-course/blob/c7090e63259ecb5d2bd84f2751cb44e0876becc2/part6_projects/production_project/project_setup.md)는
Paperclip을 별도로 복제한 뒤 기존 코드의 기능 추가·수정·삭제·리팩터링을 고민하는 실습 안내다.
조사한 디렉토리에는 이 안내와 info.md, 이미지, Excalidraw 파일이 있다.
완성된 production 전용 실행 패키지나 Paperclip 소스가 포함됐다고 해석하지 않았다.
[info.md](https://github.com/HyunjunJeon/fastcampus-harness-engineering-course/blob/c7090e63259ecb5d2bd84f2751cb44e0876becc2/part6_projects/production_project/info.md)는
외부 참고 프로젝트 링크를 제공한다. 그 링크의 기능을 강의 구현으로 취급하지 않았다.

공통화 판단: 기존 동작·테스트 기준선, 호출자/데이터/공개 계약 영향, 회귀 검증과 롤백을
PLAN에 포함한다. 품질 리뷰 → 이슈 → 동작 보존 테스트 → 작은 리팩터링 → 검증 → 회고를 반복한다.
기존 프로젝트에 새 소스 폴더나 앱 구조를 강제하지 않는다.

## Part 5 SDD 실습

- [최소 하네스](https://github.com/HyunjunJeon/fastcampus-harness-engineering-course/blob/c7090e63259ecb5d2bd84f2751cb44e0876becc2/part5/handout/03-02-minimum-harness-handout.md):
  의도와 계획, 완료 확인을 최소 요소로 보고 자동 검증과 수동 확인을 구분한다.
- [Spec / Plan / Tasks](https://github.com/HyunjunJeon/fastcampus-harness-engineering-course/blob/c7090e63259ecb5d2bd84f2751cb44e0876becc2/part5/handout/03-03-sdd-spec-plan-tasks-handout.md):
  기능의 목적·구현 전략·실행 체크리스트를 나누고 AC를 작업·테스트·QA·eval과 연결한다.
- [회고](https://github.com/HyunjunJeon/fastcampus-harness-engineering-course/blob/c7090e63259ecb5d2bd84f2751cb44e0876becc2/part5/handout/03-05-harness-retro-handout.md):
  실패를 모델/컨텍스트/하네스 관점에서 분석하고 재현·회귀 검증으로 되돌린다.
- practice의 사용자 의도 파악, Superpowers 분석, Ouroboros 분석 문서도 확인했다.
  공통 교훈은 질문 수를 늘리기보다 목표·가정·제약·미정 사항을 구조화하고 실행과 평가에 연결하는 것이다.
  해당 외부 도구의 분석은 강의 자료의 설명으로만 취급했고, 외부 런타임 전체를 독립 검증하지 않았다.

공통화 판단: SPEC은 무엇/왜, PLAN은 파일·위험·전략, TASKS는 작고 검증 가능한 작업으로 유지한다.
REQ→AC→TASK→step→검증 증거 추적표, not-run/failed/blocked 구분, 리팩터링·회고 템플릿을 추가한다.

## 원본과 사용자 포크

`git log --left-right`와 `git diff`로 확인했다. 원본 main은 포크 기준 커밋의 조상이며,
포크 쪽에만 9개 커밋(merge 포함)이 있다. 원본 대비 34개 파일이 달라졌다
(3,225줄 추가, 631줄 삭제). 이 수치는 이 PR의 변경량이 아니다.

| 항목 | 원본 기준선 | 사용자 포크의 추가·변경 | 이번 처리 |
|---|---|---|---|
| 문서 | PRD/ARCHITECTURE/ADR/UI_GUIDE와 CLAUDE 진입점 | 진입 링크·상속 설명 | 보존, 공통 흐름 연결 |
| 실행 | phase/step 순차 실행·재시도·상태·커밋 | 이슈·실제 docs 근거, 엔진 선택, Windows 처리·시간 제한 | 형식·옵션 보존, 안전 정책 교체 |
| 프로젝트 설정 | 실행기 중심 고정 설정 | harness.json + harness_config.py | 기존 값 유지 |
| 격리·상태 | Git 실행 흐름 | slot.py, status.py, worktree 강제·슬롯 잠금 | 보존 |
| 규칙 | 기본 프로젝트 지침 | rules 3계층·rule-guard·compact reload | 보존 |
| 훅 | 기본 설정 | 위험 명령·TDD·audit·issue handoff | 보존, 입력 오류/비밀 편집 차단 보강 |
| 모니터링 | 공통 실행기 | Baden HTTP 보고·task 추적·커밋 트레일러 | 보존 |
| 재사용 | 템플릿 저장소 형태 | 범용 실행 설정 | 비파괴 init/feature 명령·워크플로 템플릿 추가 |

## 안전 개선 근거와 한계

기존 포크의 ENGINES에 두 CLI의 승인 우회 옵션이 직접 들어 있었다. 프롬프트 금지 목록만으로
실행 권한을 제한할 수 없으므로 Claude는 명시적 거절 정책, Codex는 workspace-write와
네트워크 제한·승인 거절 정책을 사용한다. 위험 훅의 잘못된 입력은 차단하고 Read 외 Edit/Write에도
비밀 경로 검사를 연결한다. 엔진 실패와 completed의 충돌도 실패로 처리한다.
작업 범위 프롬프트와 regex 훅을 완전한 보안 경계로 주장하지 않는다. 자세한 정책은 SAFETY.md.

## 검증 범위

변경 전 기존 91개 테스트가 통과했다. 이번 테스트는 새 설치/기능 생성의 비파괴성·멱등성·미리보기,
경로·이슈 입력, 링크 목적지, 기존 phase 병합, 실제 execute 근거 호환,
권한 인자·잘못된 훅 입력·비밀 파일 검사·엔진 실패 상태를 검증한다.
최종 결과와 실행한 명령은 PR 설명에 기록한다. 실제 유료 에이전트 호출, 운영 DB, 배포,
외부 서비스·MCP의 권한 전체는 검증하지 않는다.
