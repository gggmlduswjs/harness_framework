# 재사용 템플릿

`project/docs/`에는 선택적으로 참고할 추가 문서도 있지만 init이 `docs/`에 생성하는 문서는
PRD(MVP 범위 포함), ROADMAP, ARCHITECTURE 3개뿐이다. ADR/UI_GUIDE/MVP_SCOPE를 자동 생성하지 않는다.

`feature/SPEC.md`는 요구사항·계획·작업·검증·완료 조건을 담은 기본 문서다.
`feature --detailed`만 별도 PLAN/TASKS/VERIFICATION/RETROSPECTIVE를 추가한다.
상세 모드의 각 문서는 SPEC에서 연결되며 별도 문서에 상세와 실제 결과를 기록한다.
기존에 생성된 문서와 실행 상태는 자동 이전하거나 덮어쓰지 않는다.

저장소 가이드: [WORKFLOW](../docs/WORKFLOW.md), [SAFETY](../docs/SAFETY.md).
설치본에서는 `templates/guides/WORKFLOW.md`, `templates/guides/SAFETY.md`를 읽는다.
