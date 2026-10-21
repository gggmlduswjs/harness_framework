# Project standardization design

Goal: reuse this repository across projects without replacing their configuration,
source layout, execution state, hooks, rules, or Baden integrations.

Selected approach: additive, versioned source bundle with a standard-library CLI.
Alternatives: documentation-only copies (cannot repeat adoption reliably), or a
new orchestrator/package manager (duplicates execute.py and requires migration).
Keep docs/PRD.md and phases/{phase}/index.json + stepN.md canonical. Add product
scope/roadmap, feature SPEC/PLAN/TASKS, verification and retrospectives under docs/.
Do not move application code or import course example business logic.

Contracts:
- init previews by default; --apply copies missing allowlisted package assets only.
  Existing files are reported and retained byte-for-byte; no force or merge option.
- feature creates one draft feature and one pending executable step, with positive
  issue number, real docs/specs evidence path, and no automatic agent invocation.
  Names are portable slugs; refuse collisions and symlink descendants.
- Claude permission mode dontAsk denies actions outside configured permissions;
  Codex explicitly requests workspace-write and never approvals. Neither engine
  receives a bypass flag. Existing CLI options, retries, logs and slot behavior stay.
- Invalid dangerous-command hook input fails closed. Hooks remain supplementary
  checks, not an OS security boundary; project config is trusted code.
- Task acceptance maps to commands/manual QA/evidence; draft scaffolding is not
  validation success. 1-to-10 work records baseline, impact, regression and rollback.

Acceptance: adoption is idempotent and non-destructive; dry run has no writes;
feature output passes existing evidence validation; old configuration unchanged;
engine invocation contains no bypass; malformed hooks block; full suite stays green.
