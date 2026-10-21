# 실행 권한과 안전 경계

## 기본 정책

- Claude: `--permission-mode dontAsk`. 프로젝트에서 허용하지 않은 도구는 거절한다.
  필요한 편집·테스트 도구 권한은 프로젝트 담당자가 구체적으로 설정한다. 광범위 Bash 허용이나
  bypassPermissions로 문제를 해결하지 않는다. 권한이 없으면 수동 세션에서 작업을 검토한다.
- Codex: `--sandbox workspace-write`, `approval_policy="never"`,
  `sandbox_workspace_write.network_access=false`를 명시한다. 추가 승인이 필요한 작업은 거절한다.
  네트워크·샌드박스 제한을 해제하는 자동 재시도나 우회 옵션은 제공하지 않는다.
- 기존 CLI, `--push`, step 상태·재시도·시간 제한·슬롯·Baden 연동은 보존한다.
  `--push`는 운영자가 명시적으로 선택한 경우에만 실행기가 수행한다.

설정된 permission 정책과 훅은 프로젝트 코드와 함께 리뷰해야 한다. 로컬·전역·조직 설정이나
MCP 도구는 별도 권한을 가질 수 있다. 이 프레임워크가 모든 외부 도구를 격리한다고 보장하지 않는다.
Claude의 permission 모드는 OS 샌드박스가 아니다. 셸 실행이 필요한 경우 실제 격리 환경과
최소 권한 도구를 사용한다. Git worktree도 보안 경계가 아니다.

## 거절·실패 처리

인증·권한이 없으면 `blocked`와 구체적 `blocked_reason`을 기록한다. 에이전트가 상태 파일을
수정할 권한도 없으면 비정상 종료/상태 미갱신으로 error가 남을 수 있다. 제한을 낮추지 말고
step 출력과 필요한 도구를 검토한 뒤 운영자가 해결하고 pending으로 재설정한다.
엔진 종료 코드가 0이 아니면 completed 보고를 인정하지 않는다. 단, completed 자체는 독립적인
테스트 증명이 아니다. 프로젝트의 검증 명령과 VERIFICATION/리뷰가 최종 판단 근거다.

Codex에서는 Claude의 block_dangerous·TDD·audit 훅이 동작하지 않는다. Codex 자체 설정과
샌드박스가 적용되며 동일한 훅 보호를 제공한다고 표기하지 않는다. git 쓰기나 테스트 환경 접근이
거절될 수 있다. 필요한 외부 작업은 별도 검토한 수동 단계로 분리한다.

## 훅의 범위

block_dangerous는 Bash/PowerShell과 Read/Edit/Write의 위험 명령·비밀 env 경로를 검사한다.
잘못된 JSON·누락되거나 잘못된 tool_input은 exit 2로 차단한다. 실행 환경 오류도 settings의
래퍼가 차단한다. 정규식 검사는 임의 코드나 인코딩을 통한 모든 우회를 막는 보안 장치가 아니다.
민감정보는 에이전트 작업 디렉토리에서 분리하고 로그·증거에 실제 비밀을 남기지 않는다.

## 확인 근거 (2026-10-21)

로컬 CLI 도움말과 공식 문서를 확인했다. 실제 엔진/API 호출을 하는 검증은 수행하지 않는다.
단위 테스트는 생성되는 인자, 훅 차단과 기존 실행 동작을 검증한다.

- [Claude CLI reference](https://code.claude.com/docs/en/cli-reference)
- [Codex CLI reference](https://developers.openai.com/codex/cli/reference/)
