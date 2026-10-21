# Harness Framework

프로젝트별 설정과 기존 실행 기능을 보존하면서, 여러 프로젝트에서 같은 문서·작업 흐름을
사용하기 위한 재사용 패키지다. Python 표준 라이브러리 기반 도입 CLI와 템플릿을 제공한다.

**PRD → MVP Scope → ROADMAP → SPEC → PLAN → TASKS → 구현 → 검증 → 리팩터링·회고**

```sh
# 기본은 미리보기; 기존 파일을 덮어쓰지 않는다.
python scripts/project.py init /path/to/project
python scripts/project.py init /path/to/project --apply
python scripts/project.py feature /path/to/project save-note --issue 123 --apply
```

- [공통 폴더·문서·0→1 및 1→10 워크플로](docs/WORKFLOW.md)
- [실행 권한·기존 환경 도입 시 주의점](docs/SAFETY.md)
- [강의 조사와 원본/포크 비교](docs/RESEARCH.md)
- [프로젝트 설정과 기존 실행기](CLAUDE.md)
- [재사용 템플릿](templates/)

기존 설정·문서·규칙은 보존하며 차이가 있는 파일은 수동 검토 대상으로 표시한다.
실행기 사용 전 프로젝트 설정과 CLI 권한을 검토한다. 템플릿 생성은 검증 완료가 아니다.

테스트: `uv run --no-project --with pytest python -m pytest scripts/ -q`
