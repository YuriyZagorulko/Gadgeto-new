# Core Principles

These rules apply universally to all work in this project.

## 1. Inspect Before Changing

Before modifying any file, model, mapping, import, or infrastructure:

- inspect the existing schema, relationships, and foreign keys;
- inspect relevant import logic;
- inspect existing migrations;
- search the codebase for existing implementations;
- inspect frontend consumers before changing API endpoints;
- inspect shared components before modifying them.

Never invent helpers, APIs, paths, modules, or functions without verifying they exist.

## 2. Stay Within Scope

Only modify files required for the requested task. Do not:

- refactor unrelated code;
- rename unrelated files;
- modify unrelated UI;
- upgrade dependencies without a reason;
- change architecture unnecessarily;
- clean unrelated technical debt.

Report unrelated issues separately instead of silently fixing them.

## 3. Preserve Existing Architecture

Reuse existing architecture when appropriate. Do not create duplicate tables,
models, utilities, or catalog data unnecessarily. Preserve existing behavior
unless a clear technical reason requires change.

## 4. Verify Your Work

After code changes:

1. Run appropriate safe tests/checks.
2. Run type checking where applicable.
3. Run linting where applicable.
4. Verify affected endpoints/pages when practical.
5. Check Docker/container health when relevant.
6. Inspect actual results.
7. Fix discovered problems when possible.

Never claim a test was performed if it was not.

Clearly distinguish:
- static inspection;
- unit tests;
- integration tests;
- E2E tests;
- real external-service tests.

HTTP `200` alone is not proof that a feature works correctly.

## 5. Report Results Accurately

After completing a task, provide:

- **Changed** — files/features changed.
- **Verified** — tests/checks actually executed and their results.
- **Not Tested** — anything that could not realistically be tested.
- **Important Notes** — unresolved issues, migrations, environment variables,
  manual steps, or risks.

Never claim completion based only on static inspection or HTTP `200`.

## 6. Temporary Files

Temporary/debug/diagnostic files must not remain in the repository after the task.

Default workflow: **CREATE → USE → DELETE**

Before finishing, inspect the working tree and remove temporary artifacts created
during the task. If a temporary file appears useful as a permanent project file,
ask permission before keeping it.

## 7. Safety First

If safety or the target environment is unclear: **STOP and ask.**

Never assume an operation is safe just because it is executed from the project
directory. Detailed safety rules are in `01-safety.md`.