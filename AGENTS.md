# AGENTS.md

## Project Role

You are working on DocFlowProject, a Django prototype for internal document workflow.

Domain context:

- company processes for engineering, repair, and maintenance of mining equipment;
- contracts;
- internal memos;
- orders;
- internal regulations, instructions, methods;
- invoices, UPD documents, and payment approval requests.

## Before Starting Work

Read these files first:

- `README.md`
- `PROJECT_CONTEXT.md`
- `ARCHITECTURE.md`
- `TASKS.md`
- `CODEX_NOTES.md`

## Technical Rules

- Main stack: Python Django.
- Prefer existing models, forms, views, services, templates, and CSS patterns.
- Do not add heavy dependencies unless they are clearly needed.
- Before committing code changes, run:

```powershell
python manage.py check
python manage.py test
```

## UX Rules

- Keep the interface simple for non-developer business users.
- Do not overload screens with unnecessary settings.
- Use Django Admin for reference data and administrative operations unless a dedicated UI is explicitly required.
- Display users as `Last name First name Patronymic`; show position under the name or in parentheses.

## Uploaded Files And MarkItDown

When the user attaches a file and asks to analyze, summarize, compare, extract requirements from, or otherwise use its contents, first try converting the file with MarkItDown.

Use:

```powershell
markitdown "FULL_PATH_TO_FILE" -o "$env:TEMP\codex-markitdown-output.md"
```

Then read the generated Markdown file and use that text as the main source of truth.

If MarkItDown fails, report the error briefly and fall back to the best available parser or direct file inspection.

Do not run MarkItDown for files where conversion is unnecessary, such as:

- plain source code files;
- small `.txt` files that are already directly readable;
- binary assets that the user wants edited visually rather than analyzed as text.

## Git

- Do not revert user changes unless explicitly requested.
- Commit only verified changes.
- Main branch: `master`.
