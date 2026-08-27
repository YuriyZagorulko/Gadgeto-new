# Development Conventions

## 1. Source File Changes

- Modify only files required for the requested task.
- Prefer minimal, targeted changes.
- Preserve existing architecture unless a clear technical reason requires change.
- Before deleting/replacing a significant file, inspect its usage and dependencies.
- Do not silently perform large refactors or unrelated cleanup.
- Do not delete important project files unless explicitly required.

## 2. Data Integrity

Before changing models, mappings, imports, or shared infrastructure:

- inspect the existing schema and relationships;
- inspect foreign keys and indexes;
- inspect relevant import logic;
- inspect existing migrations;
- search the codebase for existing implementations.

Never invent helpers, APIs, paths, modules, or functions without verifying they exist.

Reuse existing architecture when appropriate.

Do not create duplicate tables, models, utilities, or catalog data unnecessarily.

## 3. Debugging & Failure Recovery

Never blindly repeat a failed command.

When a command fails:

1. inspect the error;
2. identify the cause;
3. verify assumed files/modules/functions/containers/services;
4. change the approach when the cause is uncertain;
5. do not make unrelated code changes merely because a diagnostic command failed.

Do not run the exact same failing command more than twice without new information.

For database inspection:

- prefer the project's existing database infrastructure when verified;
- never invent database helper imports;
- inspect the project before importing helpers;
- if unclear, inspect PostgreSQL directly with `psql`;
- inspect `docker-compose.yml` for the actual DB service/container and credentials.

Do not assume the application is broken just because an inspection command failed.

A failed diagnostic command does **not** mean the import itself failed.

## 4. API Changes

Before changing an existing endpoint:

- inspect frontend consumers;
- inspect admin consumers;
- inspect backend dependencies;
- preserve compatibility when reasonably possible.

Do not silently change response formats used by existing clients.

New endpoints must:

- validate input;
- enforce authentication/authorization;
- use appropriate HTTP status codes;
- follow the project's Ukrainian UI/API messaging conventions.

## 5. Frontend / UI Changes

When changing UI:

- preserve existing behavior;
- maintain responsive behavior;
- reuse existing components/design system;
- avoid unnecessary dependencies;
- use the existing i18n/translation system;
- do not hardcode Ukrainian user-facing text when i18n already exists.

Before changing a shared component, inspect where it is used.

## 6. No Unrelated Work

Stay focused on the requested task.

Do not:

- refactor unrelated code;
- rename unrelated files;
- modify unrelated UI;
- upgrade dependencies without a reason;
- change architecture unnecessarily;
- clean unrelated technical debt.

Report unrelated issues separately instead of silently fixing them.

## 7. Temporary Artifact Cleanup

Temporary/debug/diagnostic files must not remain in the repository after the task.

Examples of temporary patterns:

- `_test*.py`, `_diag*.py`, `_debug*.py`, `_tmp*.py`, `_find*.py`, `_check*.py`
- temporary `.txt`, `.json`, `.log`, `.csv`, `.sql`
- one-off API scripts, scratch files, temporary payloads, diagnostic reports
- temporary migration/debug artifacts.

Default workflow: **CREATE → USE → DELETE**

Before finishing:

- inspect the working tree/project directories;
- remove temporary artifacts created during the task.

If a temporary file appears useful as a permanent utility/test/fixture/documentation,
ask permission before keeping it.