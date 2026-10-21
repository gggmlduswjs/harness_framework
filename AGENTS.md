# Harness project entry point

Read CLAUDE.md for project configuration, rules/INDEX.yaml and principles.md for
applicable rules, and docs/WORKFLOW.md for the document-to-execution lifecycle.
These shared rules apply to every engine; Claude hooks do not run in other engines.
Use harness.json as the existing project-specific configuration source.

Before implementation read the assigned SPEC, PLAN and TASKS under docs/specs/.
Follow the task's allowed paths and verification criteria. Record actual results
in VERIFICATION.md. Do not report scaffolding or skipped checks as completed work.
Keep existing application layout, configuration, execution state and integrations.
Never add approval/sandbox bypass flags. Stop with a concrete blocked reason when
credentials, permissions or a human decision are required. Worktrees isolate Git
changes; they are not a security sandbox.
