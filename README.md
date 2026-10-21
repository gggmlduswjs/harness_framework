# Harness Framework

기존 프로젝트 설정과 실행 기능을 보존하며 공통 문서·작업 흐름을 도입하는 재사용 패키지다.
기본 문서는 작게 유지하고, 복잡한 기능에만 상세 문서를 추가한다.

**PRD(MVP 범위 포함) → ROADMAP → 통합 SPEC → 구현·검증·완료**

```sh
# 기본은 미리보기; --apply도 기존 파일을 덮어쓰지 않는다.
python scripts/project.py init /path/to/project
python scripts/project.py init /path/to/project --apply
python scripts/project.py feature /path/to/project save-note --issue 123 --apply
# 여러 단계·의존성·검증이 필요한 복잡한 기능만 명시적으로 선택
python scripts/project.py feature /path/to/project sync-data --issue 124 --detailed --apply
```

- init의 프로젝트 문서: `docs/PRD.md`(MVP 범위 포함), `docs/ROADMAP.md`, `docs/ARCHITECTURE.md` 3개.
- feature 기본: `docs/specs/SPEC-save-note.md` 하나에 요구사항·계획·작업·검증·완료 조건.
- `--detailed`: 같은 SPEC과 `docs/specs/sync-data/` 아래 PLAN/TASKS/VERIFICATION/RETROSPECTIVE 4개.
- 두 모드 모두 기존 형식의 pending phase/step과 index 연결을 생성한다.
- 실행기·설정·규칙·훅·재사용 템플릿도 설치한다. 가이드는 `templates/guides/`에 둔다.

[공통 워크플로](docs/WORKFLOW.md) · [안전 정책](docs/SAFETY.md) ·
[조사](docs/RESEARCH.md) · [기존 실행기 설정](CLAUDE.md) · [템플릿](templates/)

기존 설정·문서·규칙은 보존하며 차이는 수동 검토 대상으로 표시한다.
기존 상세 문서와 phase는 자동 변환하지 않는다. 템플릿 생성은 검증 완료가 아니다.

테스트: `uv run --no-project --with pytest python -m pytest scripts/ -q`
Ubuntu/Windows CI에서 전체 테스트를 실행한다.
