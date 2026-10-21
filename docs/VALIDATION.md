# 검증 기록 — 공통 표준화 패키지

2026-10-21 / Windows / Python 3.13.13 / 기준 커밋 473f5f2.

| 확인 | 결과 |
|---|---|
| 변경 전 기존 전체 테스트 | 91 passed |
| 최종 scripts/ 전체 테스트 | 113 passed, 1 skipped (POSIX Git 실행 권한 테스트) |
| 수정 Python 파일 Ruff 검사 | passed |
| git diff --check | passed |
| 독립 설치본 전체 테스트 (첫 설치 검증) | 112 passed (이후 플랫폼 수정은 원본 전체 테스트로 재검증) |
| 별도 코드 리뷰 | P2 두 건 수정 후 재검토에서 추가 문제 없음 |
| 최종 설치본 도입 테스트 | 14 passed, 1 skipped |
| rule-guard 감사 | 확정 가능한 새 위반 없음; 예시·미정 규칙의 전체 준수 여부는 검사 불가 |

실행 명령:

```sh
uv run --no-project --with pytest python -m pytest scripts/ -q
uv run --no-project --with ruff python -m ruff check scripts/project.py scripts/test_project.py scripts/execute.py scripts/test_execute.py scripts/test_hooks.py .claude/hooks/block_dangerous.py
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
