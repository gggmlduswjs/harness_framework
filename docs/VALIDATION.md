# 검증 기록 — 공통 표준화 패키지

2026-10-21 / Windows / Python 3.13.13 / 기준 커밋 473f5f2.

| 확인 | 결과 |
|---|---|
| 변경 전 기존 전체 테스트 | 91 passed |
| 최종 scripts/ 전체 테스트 | 114 passed, 1 skipped (POSIX Git 실행 권한 테스트) |
| 수정 Python 파일 Ruff 검사 | passed |
| git diff --check | passed |
| 독립 설치본 전체 테스트 (첫 설치 검증) | 112 passed (이후 플랫폼 수정은 원본 전체 테스트로 재검증) |
| 별도 코드 리뷰 | P2 두 건 수정 후 재검토에서 추가 문제 없음 |
| 최종 설치본 도입 테스트 | 14 passed, 1 skipped |
| rule-guard 감사 | 확정 가능한 새 위반 없음; 예시·미정 규칙의 전체 준수 여부는 검사 불가 |

실행 명령:

```sh
uv run --no-project --with pytest python -m pytest scripts/ -q
uv run --no-project --with ruff python -m ruff check scripts/project.py scripts/test_project.py scripts/execute.py scripts/test_execute.py scripts/test_hooks.py scripts/hooks/tdd_guard.py .claude/hooks/block_dangerous.py
git diff --check
```

실제 별도 폴더에 init --apply → 설치된 project.py로 feature --issue 123 --apply를 실행했다.
생성 phase는 pending이며 기존 execute.evidence_error 검사에 통과했다.
테스트는 미리보기 무쓰기, 기존 설정·문서·훅 보존, 재실행 멱등성, phase index 병합,
잘못된 이름·이슈·index, 링크 목적지, 임시 복구 파일 보존 등을 검사한다.

안전 회귀 테스트는 구현 전 실패를 확인한 뒤 수정했다: 승인 우회 인자, 잘못된 훅 입력,
Edit/Write 비밀 경로 검사, 엔진 실패의 completed 오판, 구버전 Python 환경의 Windows junction.
POSIX 실행 권한은 Windows에서 검증할 수 없어 명시적으로 건너뛰며 Ubuntu CI에 테스트를 추가했다.
CI는 Ubuntu/Windows Python 3.11에서 전체 테스트를 실행한다. 로컬 결과와 CI 결과를 구분한다.

프로젝트별 설정 harness.json, 슬롯·상태 조회·Baden 구현은 기존 바이트를 유지한다.
실제 유료 에이전트 실행, 배포·운영 DB, 외부 도구/MCP의 전체 권한은 검증하지 않았다.
무인 실행에서 거절되는 권한은 SAFETY.md에 따라 검토 후 해결한다.

Windows Python 3.11 CI의 cp1252 환경에서 발견한 한글 JSON 출력 오류를 재현 테스트로 추가하고 수정했다.
settings 테스트 파일 읽기도 UTF-8로 명시했다. 변경 후 전체 테스트와 정적 검사를 다시 통과했다.


## 문서 기본값 간소화 — 2026-10-21

기준: PR #9의 28d0449. 기존 기록은 위에 보존한다.

- 변경 전 전체: 114 passed, 1 skipped.
- 변경 후 Windows 전체: 121 passed, 1 skipped (POSIX Git 실행 권한).
- Ruff (`scripts/project.py`, `scripts/test_project.py`) 및 `git diff --check`: 통과.
- 새 계약 테스트가 기존 구현에서 실패하는 것을 확인한 후 수정했다.
- init의 docs 직속 문서가 PRD/ROADMAP/ARCHITECTURE 3개인지, 재실행 비파괴 정책을 검사했다.
- 기본/--detailed 모두 복사된 CLI로 preview → apply → 실제 생성 파일 및 Markdown 링크를 검사했다.
- 두 모드의 phase/step은 기존 execute.evidence_error로 근거 검사를 통과했다.
- 기존 단일 SPEC/이전 기능 폴더 충돌 시 파일 및 index가 보존되는지 검사했다.
- 설치된 CLI 재사용 시 소비자의 자체 가이드가 다른 프로젝트로 복사되지 않도록 회귀 검증했다.
- 보안 보호 및 기존 실행기·슬롯·상태·Baden 회귀 테스트를 그대로 실행했다.
- 별도 읽기 전용 rule-guard/코드 리뷰의 가이드 경로·원본 선택 지적을 수정하고 재검토했다.
  새 구체적 문제는 없으며 예시·미정 규칙에 대한 기존 감사 한계는 동일하다.

Ubuntu와 Windows CI는 기존 행렬을 유지한다. 최신 커밋별 실행 결과는 PR의 Checks를 참조한다.
유료 에이전트 호출·운영 DB·배포의 종단 검증은 이번 변경에서도 실행하지 않았다.
