AGENTS.md

Build / lint / test

- Install dev deps: uv sync --extra dev
- Run full tests: uv run pytest
- Run a single test: uv run pytest tests/test_async_bash_mcp.py::test_spawn
- Lint (ruff): uv run ruff check

Code style & conventions

- Use Python 3.13+ features conservatively; maintain clear, simple code.
- Formatting: follow ruff/PEP 8. Use black-style line lengths ~88. Keep imports grouped: stdlib, third-party, local.
- Imports: always use absolute imports from package root (e.g. from async_bash_mcp import spawn).
- Types: annotate public functions and methods with type hints. Prefer built-in typing (list/dict) per py3.13.
- Naming: snake_case for functions and variables, PascalCase for classes, UPPER_SNAKE for constants.
- Errors: raise specific exceptions. Validate inputs early and return plain serializable types for MCP responses.
- Logging: prefer logging module, avoid print in library code. Keep messages concise and testable.

Agents operating here

- Follow repo scripts in pyproject.toml for entrypoints.
- No Copilot or Cursor rules found; if added later, include .github/copilot-instructions.md and .cursor/rules/* in this file.
- Store all notes about progress being make and plans in the `notes/` directory

Keep this file short and machine-readable; update when style tools change.
