Run linting and formatting checks:

1. Check code formatting: `black --check src/ tests/`
2. Run import sorting: `isort --check-only src/ tests/`
3. Execute linter: `ruff check src/ tests/`
4. Run type checker: `mypy src/`

Report any issues found and suggest fixes.
