# Project Standardization Implementation Plan

Goal: additive project bundle and traceable workflow with safe engine defaults.
Architecture: preserve existing executor and configuration; add a stdlib adoption
CLI and templates. No new runtime dependencies.
Spec: ../specs/2026-10-21-project-standard-design.md

Global constraints: do not rewrite harness.json, project rules or existing docs;
retain executor phase schema, CLI, slots and Baden behavior; no bypass switches.
Review focus: existing custom settings; symlink destinations; invalid phase index;
duplicate feature; permission-denied execution must not become completed.

- [x] Add adoption/feature behavior tests in scripts/test_project.py. Run RED.
- [x] Add scripts/project.py init/feature and templates; dry run by default,
      exclusive missing-file creation, collision preflight and existing index merge.
- [x] Add regression tests for engine policy and malformed hook input. Run RED.
- [x] Change explicit engine permission arguments and fail-closed hook input only.
- [x] Document workflow, installation/update conflicts, source comparison and safety.
- [x] Run full scripts/ suite, lint changed Python, real temporary adoption and phase
      evidence validation. Review diff; commit, push, create and attach PR.

Validation and independent review completed; publishing this branch as requested.
