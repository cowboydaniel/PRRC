# Repository Contributor Guidance

## Scope Rules
- This file governs the entire repository unless a subdirectory contains its own `AGENTS.md`. In that case, the more specific file overrides or augments these directions for files within its directory tree.
- When editing multiple files, ensure that you follow the instructions for each file based on its location in the directory hierarchy.

## Code Style & Conventions
- Python code must target Python 3.9+ and follow [PEP 8] formatting guidelines.
- Prefer dataclasses or typed NamedTuples for structured data, and include type hints on public functions and methods.
- Keep functions small and purposeful; favor pure functions where practical and avoid side effects in utility modules.
- Document non-trivial functions and modules with docstrings that describe inputs, outputs, and side effects.
- Validate critical logic with explicit unit tests located under the mirrored path in `tests/`.

## Testing Expectations
- All Python changes must be covered by tests executed with `pytest` from the repository root.
- When new behavior is introduced, add or update tests to demonstrate the expected outcomes and edge cases.
- Ensure existing tests remain green before submitting work; if a failure cannot be resolved, include context and justification in the PR discussion.

## Pull Request Requirements
- Summaries should state the problem solved and the approach taken; link to relevant issues when available.
- Call out security, performance, and operational impacts explicitly.
- Include screenshots or terminal output for user-facing changes when applicable.
- Confirm that required tests and linters have been run locally and note any deviations.
