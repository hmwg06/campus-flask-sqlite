# Single-file app Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans for this refactor.

**Goal:** Put all production Python logic in `app.py`, with direct route bodies and short Vietnamese section comments.

**Architecture:** Inline feature handlers into the existing factory and move database, catalog, shared helpers and NEU import functions into the same file. Keep templates, SQL schema and source JSON as data files. Preserve the old NEU command scripts as small entry points; keep `seed_data.py` as an optional test fixture generator.

**Tech Stack:** Existing Flask, sqlite3, unittest; standard-library argparse for optional maintenance commands.

**Spec:** User asks to consolidate all functionality into app.py and simplify the code, attaching refresh_neu_data.py.

## Global Constraints

- Preserve existing routes, permissions, CSRF, database and create_app(test_config=None).
- Do not run cleanup or imports on the live database during this refactor.
- Preserve backups, validation and rollback on mixed real/demo references.
- No new dependencies or Blueprint.

## Review Focus

- Factory isolation and direct handler bindings: route map and existing 17 tests.
- Schema/data paths after moving functions: startup and import tests.
- Backup and upload cleanup: new end-to-end test using only temporary data.
- Old script imports and commands: keep compatible public imports and main entry points.
- Default startup must never invoke maintenance operations.

## Task: Consolidate and verify

- [x] Snapshot source and route map.
- [x] Move production functions/catalog to app.py; inline route bodies and database registration; move schema to root; remove obsolete campus Python files.
- [x] Keep small legacy NEU command scripts, update test/seed imports and README.
- [x] Test backup/cleanup on temporary data; verify route map, existing behavior and CLI help.
- [x] Review the complete change.

## Verification and decisions

- All 22 routes and the form catalog match the previous application.
- All 35 feature/helper function bodies and signatures match the previous modules.
- Full refresh on temporary data verifies the database backup, all six demo-file backups, deletion of only demo uploads, preserved admin/46 real programs and 73 imported lecturer profiles.
- New refresh test initially failed Windows temporary-directory cleanup because SQLite connection context managers do not close connections. Both backup commands and the test now use `contextlib.closing`; rerun passed.
- CLI help initially failed on Windows cp1252 stdout. A regression test reproduced it; ASCII command help fixes it while website text remains Vietnamese. Actual `app.py --help` now exits successfully.
- Final full suite: 20 tests passed in 29.819 seconds. Diff whitespace checks passed.
- Independent static review found no actionable correctness regressions in imports, bindings, paths, factory isolation, maintenance sequencing or legacy entrypoints.
- Ruling: keep old NEU scripts as short compatible entrypoints and the optional fixture generator separately; production logic resides in app.py. This preserves existing commands while avoiding duplicated code.
