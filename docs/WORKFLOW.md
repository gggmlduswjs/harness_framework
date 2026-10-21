# 프로젝트 공통 개발 흐름

PRD → MVP Scope → ROADMAP → SPEC → PLAN → TASKS → 구현 → 검증 → 리팩터링·회고.
프로젝트의 제품·기술 스택·소스 폴더는 유지하고 문서와 실행 산출물의 위치를 통일한다.

```text
CLAUDE.md / AGENTS.md       프로젝트 진입점
harness.json                프로젝트별 실행 설정 (기존 값 보존)
rules/                      기존 3계층 규칙
docs/
  PRD.md                    사용자 문제·가치·REQ ID
  MVP_SCOPE.md              P0/P1/P2/제외·첫 성공 경험·실패 조건
  ROADMAP.md                의존 순서·기능 SPEC·종료 기준
  ARCHITECTURE.md / ADR.md / UI_GUIDE.md  기존 기술 문서
  specs/<feature>/
    SPEC.md                 무엇과 왜·계약·상태·실패·AC ID
    PLAN.md                 어떻게·파일·인터페이스·영향·롤백
    TASKS.md                작은 작업·허용 범위·실제 검증 명령·추적표
    VERIFICATION.md         AC별 실행 결과·증거·위험·리뷰
    RETROSPECTIVE.md         실패 원인·리팩터링·다음 이슈
phases/
  index.json                실행 상태의 기준
  <feature>/index.json      기존 project/phase/issue/steps 형식 유지
  <feature>/stepN.md         독립 세션에 줄 작업·SPEC 근거·AC
scripts/                    기존 실행·슬롯·상태·훅·Baden + project.py
templates/                  재사용 원본; 작성한 문서와 분리
```

## 도입과 갱신

Python 3.10 이상, Git, 기존 실행에는 uv와 Claude Code 또는 Codex CLI가 필요하다.
이 저장소를 신뢰할 수 있는 버전/커밋으로 복제한 뒤 다음을 실행한다.

```sh
python scripts/project.py init /path/to/project
python scripts/project.py init /path/to/project --apply
```

첫 명령은 미리보기다. `ADD`는 없는 파일, `KEEP same`은 같은 파일,
`KEEP different (manual review)`는 다른 기존 파일이다. `--apply`도 덮어쓰지 않는다.
설정 자동 병합이나 강제 덮어쓰기 기능은 없다. 기존 소스 이동·git 설정·에이전트 실행도 하지 않는다.
대상 경로 아래의 심볼릭 링크와 Windows junction은 거절한다.

도입 후 `harness.json`의 프로젝트 이름·슬롯·문서·검증 설정과 `rules/INDEX.yaml`의
프로젝트 이름을 실제 프로젝트에 맞춘다. 기존 파일은 그대로이므로 이미 설정했다면 유지한다.
기존 `.claude/settings.json`은 자동 병합하지 않는다. 신뢰한 패키지 버전과 비교하여
block_dangerous/TDD/audit 등 필요한 훅을 직접 통합하고 테스트한다. 소비자 레포의
AGENTS.md/CLAUDE.md가 이미 있다면 이 문서 링크와 프로젝트 지침을 직접 연결한다.
`.gitignore`도 유지하므로 패키지의 로그·출력 제외 항목을 검토해 추가한다.

업데이트도 같은 미리보기를 사용한다. 변경된 실행기·훅·템플릿은 KEEP different로 표시되므로
차이를 리뷰해서 선택적으로 반영한다. 버전은 원본 커밋 해시와 도입 PR에 기록한다.
복사된 실행기와 훅은 프로젝트의 코드다. 무인 자동 업데이트하지 않는다.
삭제·원복은 도입 PR을 기준으로 한다. 사용자 문서와 프로젝트 설정을 일괄 삭제하지 않는다.

## 0→1: 아이디어를 실행 가능한 작업으로

1. PRD에서 첫 사용자·문제·한 가지 성공 경험·성공 지표·REQ ID를 정한다.
2. MVP_SCOPE에서 P0와 후순위/제외를 고정하고 실패·권한·데이터 기록을 정한다.
3. ROADMAP에서 의존 순서와 각 단계의 종료 증거를 연결한다.
4. 실제 GitHub 이슈 번호로 기능 초안을 만든다.

```sh
python scripts/project.py feature /path/to/project save-note --issue 123
python scripts/project.py feature /path/to/project save-note --issue 123 --apply
```

SPEC/PLAN/TASKS/검증/회고와 `phases/save-note/step0.md`를 만든다.
기존 기능과 같은 이름은 거절하고 기존 phase index의 다른 필드와 항목은 보존한다.
생성 명령은 단일 작성자가 실행한다. 실행기나 다른 생성 작업과 동시에 index를 수정하지 않는다.
파일 쓰기 중 OS 오류가 나면 일부 파일이 남을 수 있으므로 git diff로 확인한다.

5. 초안의 미정 항목을 채운다. SPEC의 AC → TASK → 테스트/수동 QA/eval → 증거를 연결한다.
   TASK는 한 가지 결과를 낼 크기로 나누고 파일 범위, 의존성, 실제 명령, 중단 조건을 적는다.
   단계가 늘어나면 `step1.md` 등과 phase의 steps 배열을 함께 추가한다.
6. 계획을 리뷰한 뒤 기존 슬롯 worktree에서 실행한다. 필요 권한은 [SAFETY](SAFETY.md)를 따른다.

```sh
uv run python scripts/slot.py open <제품>-<레이어>
# 해당 슬롯 worktree에서:
python scripts/execute.py save-note
python scripts/execute.py save-note --engine codex
python scripts/status.py
```

`evidence.pattern`이 기본 `docs/` 경로를 인식하므로 `docs/specs/<feature>/SPEC.md`를
실제 근거로 참조한다. ROADMAP은 실행 순서 문서이고 기능 근거가 아니다.
기존 evidence 설정이 별도 패턴이면 프로젝트 담당자가 호환되도록 검토한다.
생성된 초안은 실행을 준비한 문서일 뿐이다. 미정 상태에서 구현하거나 통과를 기록하지 않는다.

7. 실제 검증과 수동 QA를 실행하고 VERIFICATION에 명령·종료 코드·AC별 결과·증거를 남긴다.
   index의 completed는 에이전트 보고이므로 검증 문서와 diff를 따로 리뷰한다.
8. PR 리뷰와 통합 후 회고에서 실패를 재현 가능한 회귀 테스트·규칙·다음 작업으로 바꾼다.

## 1→10: 기존 제품을 안전하게 바꾸기

기존 프로젝트에는 새 앱 골격을 강요하지 않는다. 먼저 현재 실행법·기준선 테스트·사용자 흐름을
기록한다. PLAN에 호출자·데이터·공개 계약·호환성·성능·배포 영향과 복구 방법을 추가한다.
품질 리뷰에서 발견한 문제를 이슈로 분리하고, 동작을 고정하는 테스트 후 작은 리팩터링을 한다.
새 기능이나 동작 변경은 SPEC과 AC부터 갱신한다. 기존 실패는 변경으로 해결됐다고 주장하지 않는다.

회고에는 무엇을 위임했고 사람이 무엇을 판단했는지, 반복 실패가 모델·컨텍스트·하네스·제품 코드
어디에서 시작됐는지, 다음 실행에서 확인할 회귀 사례가 무엇인지 기록한다.

## 문서 중복 방지

PRD는 제품 요구, SPEC은 기능 계약, PLAN은 구현 전략, TASKS는 실행 체크리스트다.
phases는 실행 상태와 독립 세션 입력을 가진다. TASKS 추적표로 서로 연결하고 상태를 여러 곳에서
손으로 동기화하지 않는다. ADR과 아키텍처는 기존 위치를 유지한다. 강의의 번호식 파일명과
최상위 specs/tasks 구조를 그대로 복제하지 않고 현재 execute.py의 docs 근거 규칙에 맞췄다.
