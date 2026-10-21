# Template bundle

`project/`는 신규 도입 시 생성할 프로젝트 문서, `feature/`는 기능별 문서 원본이다.
설치/기능 생성은 `scripts/project.py`를 사용한다. 기존 파일을 덮어쓰지 않는다.
공통 프로세스는 `docs/WORKFLOW.md`를 따른다.

0→1은 PRD/MVP_SCOPE/ROADMAP부터, 1→10은 기존 제품 요구를 확인하고 PLAN의
기준선·영향 범위·호환성·롤백부터 구체화한다. 동일 템플릿을 쓰되 해당 없는 항목은 이유를 적는다.
모든 문서는 초안이다. 실제 프로젝트 이름·요구 ID·경로·검증 명령·결과를 채운 뒤 사용한다.
TASKS의 추적표와 `phases/<feature>/stepN.md`를 연결하며 검증 전 완료 표시하지 않는다.
