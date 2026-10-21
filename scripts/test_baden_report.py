"""baden_report.py 핵심: 깨지면 rule-guard 보고가 작업을 막거나 깨진 JSON 이 나간다.

- 서버가 꺼져 있어도 exit 0 + 「미기록」.
- 따옴표·역슬래시·개행·한글 reason 이 그대로 왕복하고, 안 준 severity 는 본문에 없다.
실행: uv run --no-project --with pytest python -m pytest scripts/test_baden_report.py -q
"""

import json
import os
import socket
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

SCRIPT = Path(__file__).parent / "baden_report.py"


def run(url, *args):
    env = {**os.environ, "BADEN_URL": url, "BADEN_TASK_ID": "t-1"}
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args], capture_output=True, text=True, encoding="utf-8", env=env, timeout=10
    )


def test_server_down_exit0():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()  # 닫힌 포트 — 연결 거부
    r = run(f"http://127.0.0.1:{port}/api/query", "--action", "rule_pass", "--rule", "C1")
    assert r.returncode == 0
    assert "미기록" in r.stdout


def test_payload_roundtrip():
    got = []

    class H(BaseHTTPRequestHandler):
        def do_POST(self):
            got.append(self.rfile.read(int(self.headers["Content-Length"])))
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'{"ok":true}')

        def log_message(self, *a):
            pass

    srv = HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.handle_request, daemon=True).start()
    reason = '원문 "MUST NOT" \\ 경로 C:\\x\n둘째 줄'
    r = run(f"http://127.0.0.1:{srv.server_port}/api/query", "--action", "check_rule", "--rule", "C1", "--reason", reason)
    srv.server_close()
    assert r.returncode == 0 and "기록됨 200" in r.stdout
    body = json.loads(got[0].decode("utf-8"))
    assert body["reason"] == reason
    assert (body["projectName"], body["taskId"], body["action"]) == (
        json.loads((SCRIPT.parent.parent / "harness.json").read_text(encoding="utf-8"))["project"],
        "t-1",
        "check_rule",
    )
    assert "severity" not in body
