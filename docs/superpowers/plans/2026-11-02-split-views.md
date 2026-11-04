# Split views Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans to implement this refactor inline.

**Goal:** Keep URL declarations in `app.py` and separate feature handlers into Python files.

**Architecture:** `create_app()` registers explicit `@app.route` wrappers that call feature modules. Feature modules use shared helpers and SQLite without importing `app.py`.

**Tech Stack:** Existing Flask, SQLite, unittest; no new dependencies.

**Spec:** User request: “app.py sẽ gọi các đường dẫn và mỗi tính năng chia ra thành các file .py riêng”.

## Global Constraints

- Preserve URLs, endpoint names, HTTP methods, authorization, CSRF and existing data.
- Keep `create_app(test_config=None)` and support multiple independent test apps.
- Use ordinary functions and explicit imports; no Blueprint.

## Review Focus

- URL and method preservation: compare complete route maps before and after.
- Login redirects, POST CSRF, revoked sessions: existing `tests/test_app.py`.
- Feature imports and templates: existing all-pages and form tests.
- Role restrictions and uploads: existing access and upload tests.
- Directory and database isolation: existing `tests/test_neu_directory.py` and reopening tests.

## Task: Separate handlers and centralize URL registration

**Files:**
- Modify `app.py`: configuration, hooks, explicit URL wrappers.
- Create `campus/auth.py`, `dashboard.py`, `students.py`, `training.py`, `learning.py`, `reports.py`, `accounts.py`: corresponding handlers with existing names and arguments.
- Create `campus/records.py`: shared listing/edit handlers and form validation.
- Create `campus/common.py`: query, permission, visibility and select-option helpers.
- Create `campus/hooks.py`: authentication, response headers, template context, error handlers.
- Remove `campus/views.py` once all callers use the new files.
- Update `README.md`: structure and request-flow example.

**Interfaces:** Preserve handler names and parameters from `campus/views.py`. Routes call them through module imports; handlers return the same Flask responses.

- [x] Capture route map and function bodies for comparison.
- [x] Move handlers and helpers, preserving business logic; register wrappers in `app.py`.
- [x] Document structure and remove the obsolete module.
- [x] Compare routes/function bodies, run `unittest discover -s tests`, inspect diff.

## Verification

- All 22 URL, endpoint and HTTP-method entries match the pre-refactor snapshot.
- All 34 moved functions retain the same arguments and body AST.
- Existing suite: 17 tests passed (21.471 seconds).
- `git diff --check` passed; no remaining imports of the removed module in application or test code.
