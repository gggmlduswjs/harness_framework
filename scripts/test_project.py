"""Adoption must preserve consumer projects; generated phases reuse execute.py."""
import json
import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "scripts/project.py"


def run(*args):
    return subprocess.run([sys.executable, str(CLI), *map(str, args)],
                          capture_output=True, text=True, encoding="utf-8", check=False)


def test_preview_is_read_only_and_apply_is_idempotent(tmp_path):
    target = tmp_path / "consumer"
    preview = run("init", target)
    assert preview.returncode == 0, preview.stderr
    assert not target.exists()
    applied = run("init", target, "--apply")
    assert applied.returncode == 0, applied.stderr
    assert {p.name for p in (target / "docs").iterdir()} == {"PRD.md", "ROADMAP.md", "ARCHITECTURE.md"}
    assert (target / "scripts/execute.py").is_file()
    assert (target / ".claude/hooks/block_dangerous.py").is_file()
    assert (target / "templates/feature/SPEC.md").is_file()
    before = {p.relative_to(target): p.read_bytes() for p in target.rglob("*") if p.is_file()}
    assert run("init", target, "--apply").returncode == 0
    assert before == {p.relative_to(target): p.read_bytes() for p in target.rglob("*") if p.is_file()}


@pytest.mark.skipif(os.name == "nt", reason="POSIX executable bits are not supported on Windows")
def test_new_git_hook_is_executable_and_existing_hook_mode_is_preserved(tmp_path):
    assert run("init", tmp_path, "--apply").returncode == 0
    hook = tmp_path / "scripts/githooks/prepare-commit-msg"
    assert hook.stat().st_mode & stat.S_IXUSR
    hook.chmod(0o640)
    assert run("init", tmp_path, "--apply").returncode == 0
    assert stat.S_IMODE(hook.stat().st_mode) == 0o640


def test_existing_config_docs_and_settings_are_retained(tmp_path):
    files = {"harness.json": b'{"project":"custom","private":true}',
             "docs/PRD.md": "기존 기획".encode(),
             ".claude/settings.json": b'{"hooks":{"custom":[]}}',
             "rules/INDEX.yaml": b"project: custom\n"}
    for rel, content in files.items():
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(content)
    result = run("init", tmp_path, "--apply")
    assert result.returncode == 0, result.stderr
    assert "KEEP" in result.stdout
    for rel, content in files.items():
        assert (tmp_path / rel).read_bytes() == content


def test_feature_keeps_existing_phase_and_satisfies_executor_evidence(tmp_path):
    assert run("init", tmp_path, "--apply").returncode == 0
    phases = tmp_path / "phases"
    phases.mkdir()
    (phases / "index.json").write_text(json.dumps({"custom": 42, "phases": [
        {"dir": "old", "status": "completed"}]}), encoding="utf-8")
    assert run("feature", tmp_path, "save-note", "--issue", 12).returncode == 0
    assert not (tmp_path / "docs/specs").exists()
    result = run("feature", tmp_path, "save-note", "--issue", 12, "--apply")
    assert result.returncode == 0, result.stderr
    idx = json.loads((phases / "index.json").read_text())
    assert idx["custom"] == 42 and idx["phases"][0]["dir"] == "old"
    assert idx["phases"][1] == {"dir": "save-note", "status": "pending"}
    sys.path.insert(0, str(ROOT / "scripts"))
    import execute
    assert execute.evidence_error(phases / "save-note", ("docs/PRD.md",)) is None
    before = (phases / "index.json").read_bytes()
    assert run("feature", tmp_path, "save-note", "--issue", 12, "--apply").returncode != 0
    assert (phases / "index.json").read_bytes() == before


@pytest.mark.parametrize("slug", ["../escape", "a/b", "CON", "Upper", "a.b"])
def test_rejects_nonportable_feature_names(tmp_path, slug):
    assert run("feature", tmp_path, slug, "--issue", 1, "--apply").returncode != 0
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("issue", [0, -1])
def test_issue_must_be_positive(tmp_path, issue):
    assert run("feature", tmp_path, "demo", "--issue", issue, "--apply").returncode != 0
    assert not list(tmp_path.iterdir())


def test_corrupt_index_does_not_partially_create_feature(tmp_path):
    (tmp_path / "phases").mkdir()
    (tmp_path / "phases/index.json").write_text('{"phases": "invalid"}')
    assert run("feature", tmp_path, "demo", "--issue", 1, "--apply").returncode != 0
    assert not (tmp_path / "docs").exists()


def test_stale_temporary_index_is_preserved_without_partial_writes(tmp_path):
    (tmp_path / "phases").mkdir()
    temp = tmp_path / "phases/index.json.harness-tmp"
    temp.write_bytes(b"existing recovery data")
    result = run("feature", tmp_path, "demo", "--issue", 1, "--apply")
    assert result.returncode != 0 and "stale" in result.stderr
    assert temp.read_bytes() == b"existing recovery data"
    assert not (tmp_path / "docs").exists()


def test_symlink_destination_is_refused(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    target = tmp_path / "target"
    target.mkdir()
    try:
        (target / "docs").symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("OS does not permit creating symlinks")
    assert run("init", target, "--apply").returncode != 0
    assert not list(outside.iterdir())
    assert not (target / "harness.json").exists()


@pytest.mark.skipif(os.name != "nt", reason="Windows junction behavior")
def test_internal_junction_refused_without_path_is_junction(tmp_path, monkeypatch):
    sys.path.insert(0, str(ROOT / "scripts"))
    import project

    storage = tmp_path / "storage"
    storage.mkdir()
    junction = tmp_path / "docs"
    result = subprocess.run(["cmd", "/c", "mklink", "/J", str(junction), str(storage)],
                            capture_output=True, check=False)
    assert result.returncode == 0
    # Python 3.10/3.11 lack Path.is_junction; emulate that missing protection.
    monkeypatch.setattr(Path, "is_junction", lambda self: False, raising=False)
    with pytest.raises(ValueError, match="linked destination"):
        project.safe_path(tmp_path, Path("docs/PRD.md"))
    assert not list(storage.iterdir())


@pytest.mark.parametrize("detailed", [False, True])
def test_feature_document_modes_and_installed_cli(tmp_path, detailed):
    assert run("init", tmp_path, "--apply").returncode == 0
    installed = tmp_path / "scripts/project.py"
    args = ["feature", str(tmp_path), "demo", "--issue", "12"]
    if detailed:
        args.append("--detailed")
    preview = subprocess.run([sys.executable, str(installed), *args], capture_output=True, check=False)
    assert preview.returncode == 0, preview.stderr
    assert not (tmp_path / "docs/specs").exists()
    applied = subprocess.run([sys.executable, str(installed), *args, "--apply"], capture_output=True, check=False)
    assert applied.returncode == 0, applied.stderr
    specs = tmp_path / "docs/specs"
    expected = {"SPEC-demo.md"}
    if detailed:
        expected.add("demo")
        assert {p.name for p in (specs / "demo").iterdir()} == {
            "PLAN.md", "TASKS.md", "VERIFICATION.md", "RETROSPECTIVE.md"}
    assert {p.name for p in specs.iterdir()} == expected
    spec = (specs / "SPEC-demo.md").read_text(encoding="utf-8")
    assert "{{" not in spec
    # Markdown links in generated documents must resolve in the installed project.
    import re
    for document in specs.rglob("*.md"):
        for link in re.findall(r"\]\(([^)]+)\)", document.read_text(encoding="utf-8")):
            assert (document.parent / link).is_file(), (document, link)
    # A copied CLI can also repeat init without missing its reference guides.
    assert subprocess.run([sys.executable, str(installed), "init", str(tmp_path)],
                          capture_output=True, check=False).returncode == 0
    step = (tmp_path / "phases/demo/step0.md").read_text(encoding="utf-8")
    for line in step.splitlines():
        if line.startswith("- docs/"):
            assert (tmp_path / line[2:]).is_file(), line
    sys.path.insert(0, str(ROOT / "scripts"))
    import execute
    assert execute.evidence_error(tmp_path / "phases/demo", ("docs/PRD.md",)) is None


@pytest.mark.parametrize("existing", ["docs/specs/SPEC-demo.md", "docs/specs/demo/PLAN.md"])
@pytest.mark.parametrize("detailed", [False, True])
def test_feature_preserves_existing_documents_without_partial_writes(tmp_path, existing, detailed):
    path = tmp_path / existing
    path.parent.mkdir(parents=True)
    path.write_bytes(b"user content")
    args = ["feature", tmp_path, "demo", "--issue", 12, "--apply"]
    if detailed:
        args.append("--detailed")
    assert run(*args).returncode != 0
    assert path.read_bytes() == b"user content"
    assert not (tmp_path / "phases").exists()


def test_installed_cli_reuses_package_guides_instead_of_consumer_docs(tmp_path):
    consumer = tmp_path / "consumer"
    assert run("init", consumer, "--apply").returncode == 0
    guide = consumer / "templates/guides/WORKFLOW.md"
    (consumer / "docs/WORKFLOW.md").write_bytes(b"private consumer guide")
    second = tmp_path / "second"
    result = subprocess.run([sys.executable, str(consumer / "scripts/project.py"),
                             "init", str(second), "--apply"], capture_output=True, check=False)
    assert result.returncode == 0, result.stderr
    assert (second / "templates/guides/WORKFLOW.md").read_bytes() == guide.read_bytes()
