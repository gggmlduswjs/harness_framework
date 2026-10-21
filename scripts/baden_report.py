"""Baden HTTP 보고 — MCP 도구를 못 쓰는 서브에이전트(rule-guard 등)용.

uv run --no-project --quiet python scripts/baden_report.py --action rule_violation \
    --rule C1 --severity high --target src/x.py:42 --reason "..."

- 본문은 json.dumps 로 만든다 — 셸 인용·JSON escape 를 손으로 하지 않는다.
- 3초 타임아웃, 재시도 없음. 네트워크·서버 문제는 「미기록 <사유>」 한 줄 + exit 0(호출자를 막지 않는다).
- 잘못된 사용(모르는 action 등)은 호출자 버그라 argparse 가 exit 2 로 끊는다 — 보내지 않는다.
- 서버는 등록 안 된 projectName 도 200 으로 받고 버린다. 「기록됨 200」 = 서버가 받았다는 뜻까지만.
"""

import argparse
import json
import os
import sys
import urllib.request
from datetime import datetime

from harness_config import ROOT

# Baden 은 action 문자열로 위반을 센다 — 'violation' 이 든 이름은 전부 위반이다(fix 에 넣지 말 것).
ACTIONS = ["check_rule", "rule_pass", "rule_violation", "fix_rule", "review_pass", "review_issue"]
SEVERITIES = ["critical", "high", "medium", "low"]
DEFAULT_URL = "http://127.0.0.1:3800/api/query"


def main(argv=None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(description="Baden /api/query 로 보고 1건")
    p.add_argument("--action", required=True, choices=ACTIONS)
    p.add_argument("--rule", help="ruleId (review_* 는 rule-guard)")
    p.add_argument("--severity", choices=SEVERITIES)
    p.add_argument("--target", help="파일:줄")
    p.add_argument("--reason")
    p.add_argument("--task", help="taskId — 없으면 BADEN_TASK_ID, 그것도 없으면 새로 만든다")
    a = p.parse_args(argv)

    try:
        project = json.loads((ROOT / "harness.json").read_text(encoding="utf-8"))["project"]
    except (OSError, ValueError, KeyError) as e:
        print(f"미기록 harness.json project 를 못 읽음: {e}")
        return 0

    task = a.task or os.environ.get("BADEN_TASK_ID")
    if not task:
        task = datetime.now().strftime("rule-guard-%Y%m%d-%H%M%S")
        print(f"taskId {task} — 이후 보고에 --task {task} 로 같은 값을 넘겨라")

    body = {
        "projectName": project,
        "taskId": task,
        "action": a.action,
        "ruleId": a.rule,
        "severity": a.severity,
        "target": a.target,
        "reason": a.reason,
    }
    data = json.dumps({k: v for k, v in body.items() if v is not None}, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        os.environ.get("BADEN_URL", DEFAULT_URL),
        data=data,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=3) as r:
            print("기록됨 200" if r.status == 200 else f"미기록 HTTP {r.status}")
    except Exception as e:  # 연결 거부·시간 초과·비200(HTTPError) 전부 — 작업을 막지 않는다
        print(f"미기록 {type(e).__name__}: {e}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
