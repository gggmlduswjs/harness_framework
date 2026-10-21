"""훅 회귀 테스트: block_dangerous(차단·오탐) · audit_log(비밀 가림) · tdd_guard(테스트 강제).

깨지면: rm -rf·force push·운영 psql·.env 읽기가 그냥 통과하거나, 평소 작업(.env.example 복사·
커밋 메시지)이 막히거나, API 키·토큰이 audit.jsonl 에 평문으로 남거나, 규칙 코드가 테스트 없이 고쳐진다.
실행: uv run pytest scripts/test_hooks.py
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
BLOCK = ROOT / ".claude" / "hooks" / "block_dangerous.py"
AUDIT = ROOT / "scripts" / "hooks" / "audit_log.py"


def _block_rc(tool_input: dict) -> int:
    r = subprocess.run(
        [sys.executable, "-I", str(BLOCK)],
        input=json.dumps({"tool_input": tool_input}),
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return r.returncode


@pytest.mark.parametrize(
    "command",
    [
        "rm -rf build",
        "rm -Rf x",
        "rm -r -f x",
        "rm --recursive --force x",
        "Remove-Item -Recurse -Force x",
        "git push --force origin main",
        "git push origin main -f",
        "git reset --hard HEAD~1",
        "psql -c 'DROP TABLE x'",
        "psql -h db.abc.supabase.co -U postgres",
        "psql -h prod-db -U app",
        "cat .env",
        "Get-Content apps/api/.env.local",
        "type .env.production",
        'cat ".env"',
        "grep KEY .env",
        "rg -n token apps/api/.env.local",
        "sed -n 1p .env",
        "git push -uf origin main",
        "git push origin +main",
    ],
)
def test_blocks_dangerous(command):
    assert _block_rc({"command": command}) == 2


@pytest.mark.parametrize(
    "command",
    [
        "cp .env.example .env",
        "grep -rn '.env' docs/",
        "rg -n 'load .env' src",
        'git commit -m "docs: cat .env 금지, rm -rf 막기"',
        "gh pr create --body 'type .env 방지, cat .env 막음'",
        "cat .env.example",
        "cat apps/web/.env.mock",
        'psql -h localhost -d app -c "select count(*) from products"',
        "rm -r build",
        "git push origin feat",
        'grep -rn "rm -rf" scripts',
        "git grep 'git reset --hard'",
        "Select-String -Path x.md -Pattern 'rm -rf'",
    ],
)
def test_allows_normal_work(command):
    assert _block_rc({"command": command}) == 0


@pytest.mark.parametrize(
    ("path", "rc"),
    [
        ("C:\\repo\\.env", 2),
        ("/repo/apps/api/.env.local", 2),
        ("/repo/apps/web/.env.mock", 0),
        ("/repo/.env.local.example", 0),
        ("/repo/.env.template", 0),
        ("/repo/README.md", 0),
    ],
)
def test_read_env_file(path, rc):
    assert _block_rc({"file_path": path}) == rc


def test_audit_log_redacts_secrets(tmp_path):
    (tmp_path / ".claude").mkdir()
    secrets = {
        "curl -H 'Authorization: Bearer abc.def.ghi' https://x": "abc.def.ghi",
        "export SHOP_ACCESS_KEY=a1b2c3d4e5": "a1b2c3d4e5",
        "SHIP_CLIENT_SECRET = 'q w e'": "q w e",
        "curl -u admin:s3cr3tpass https://x": "s3cr3tpass",
        "aws s3 ls --key AKIAIOSFODNN7EXAMPLE": "AKIAIOSFODNN7EXAMPLE",
        "psql postgresql://u:pw@db.supabase.co/postgres": "pw@db",
        """curl -d '{"password":"hunter2x"}' https://x""": "hunter2x",
    }
    for cmd in secrets:
        subprocess.run(
            [sys.executable, "-I", str(AUDIT)],
            input=json.dumps({"tool_name": "Bash", "tool_input": {"command": cmd}}),
            text=True,
            encoding="utf-8",
            env={"CLAUDE_PROJECT_DIR": str(tmp_path), "SYSTEMROOT": "C:\\Windows"},
            check=True,
        )
    lines = (tmp_path / ".claude" / "audit.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == len(secrets)
    for line, secret in zip(lines, secrets.values(), strict=True):
        args = json.loads(line)["args"]
        assert secret not in args and "[REDACTED]" in args


def _tdd_denies(proj: Path, tool_input: dict, enabled: bool = True) -> bool:
    cfg = {
        "tdd_guard": {
            "enabled": enabled,
            "targets": ["src/*/service.py"],
            "tests": ["tests/**/{parent}/test_{mod}.py"],
        }
    }
    (proj / "harness.json").write_text(json.dumps(cfg), encoding="utf-8")
    r = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "hooks" / "tdd_guard.py")],
        input=json.dumps({"tool_input": tool_input}),
        capture_output=True,
        text=True,
        encoding="utf-8",
        env={**os.environ, "CLAUDE_PROJECT_DIR": str(proj)},
    )
    assert r.returncode == 0, r.stderr
    return '"permissionDecision": "deny"' in r.stdout


def test_tdd_guard_denies_without_exact_test(tmp_path):
    """깨지면: 규칙 코드가 테스트 없이 고쳐진다 — test_ 폴더 아래·다른 모듈 테스트·경로 없음."""
    proj = tmp_path / "test_proj"  # test_ 로 시작하는 폴더(pytest 임시 폴더) 아래
    proj.mkdir()
    target = {"file_path": str(proj / "src" / "app" / "order" / "service.py")}
    assert not _tdd_denies(proj, target, enabled=False)  # 꺼져 있으면 통과(새 틀 기본값)
    assert _tdd_denies(proj, target)
    other = proj / "tests" / "order" / "test_service_area.py"  # 다른 모듈 테스트
    other.parent.mkdir(parents=True)
    other.write_text("def test_x(): pass\n", encoding="utf-8")
    assert _tdd_denies(proj, target)
    assert _tdd_denies(proj, {})  # file_path 를 못 읽으면 통과시키지 않는다
    assert not _tdd_denies(proj, {"file_path": str(proj / "src" / "app" / "view.py")})
    (other.parent / "test_service.py").write_text("def test_x(): pass\n", encoding="utf-8")
    assert not _tdd_denies(proj, target)


