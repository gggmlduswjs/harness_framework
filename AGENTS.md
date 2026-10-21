# Harness project entry point

Read CLAUDE.md for project configuration, rules/INDEX.yaml and principles.md for
applicable rules, and docs/WORKFLOW.md for the document-to-execution lifecycle
(installed projects: templates/guides/WORKFLOW.md).
These shared rules apply to every engine; Claude hooks do not run in other engines.
Use harness.json as the existing project-specific configuration source.

Before implementation read the assigned docs/specs/SPEC-<feature>.md.
It includes requirements, plan, tasks, verification and completion criteria.
Only --detailed features add separate PLAN/TASKS/VERIFICATION/RETROSPECTIVE
under docs/specs/<feature>/; follow those linked documents when present.
Follow the task's allowed paths and verification criteria. Record actual results
in the SPEC verification section (or linked VERIFICATION.md in detailed mode).
Do not report scaffolding or skipped checks as completed work.
Keep existing application layout, configuration, execution state and integrations.
Never add approval/sandbox bypass flags. Stop with a concrete blocked reason when
credentials, permissions or a human decision are required. Worktrees isolate Git
changes; they are not a security sandbox.
