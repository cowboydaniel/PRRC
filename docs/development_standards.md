# PRRC Development Standards
**HQ Command GUI & FieldOps Development Guidelines**
**Phase 0: Coding Standards & Best Practices**
**Last Updated:** 2025-11-02

---

## Table of Contents
1. [Branch Naming Conventions](#branch-naming-conventions)
2. [Commit Message Standards](#commit-message-standards)
3. [Code Style Guide](#code-style-guide)
4. [Documentation Standards](#documentation-standards)
5. [Testing Requirements](#testing-requirements)
6. [Review Process](#review-process)
7. [Security Guidelines](#security-guidelines)

---

## Branch Naming Conventions

### Format
```
<type>/<description>-<session-id>

Types:
  claude/      - AI-assisted development branches (with session ID)
  feature/     - New feature development
  bugfix/      - Bug fixes
  hotfix/      - Emergency production fixes
  refactor/    - Code refactoring (no new features)
  docs/        - Documentation updates
  test/        - Test improvements
  chore/       - Build, tooling, dependency updates
```

### Examples
```
claude/phase-0-foundation-011CUiwcWoFw17JYEeDFiUc5
feature/hq-command-telemetry-dashboard
bugfix/qt-compat-pyside6-import
hotfix/critical-scheduling-null-pointer
refactor/extract-gui-components
docs/phase-1-ui-specifications
test/increase-coverage-hq-analytics
chore/upgrade-pyside6-6.7
```

### Branch Lifecycle
1. **Create** from `main` or `dev` branch
2. **Develop** with frequent commits
3. **Push** to remote for backup and collaboration
4. **Pull Request** when ready for review
5. **Merge** after approval and CI/CD passes
6. **Delete** after successful merge

### Protected Branches
- `main` - Production-ready code (requires PR + review)
- `dev` - Integration branch (requires PR + review)

---

## Commit Message Standards

### Format (Conventional Commits)
```
<type>(<scope>): <subject>

[optional body]

[optional footer(s)]
```

### Types
| Type | Description | Example |
|------|-------------|---------|
| `feat` | New feature | `feat(hq-gui): Add roster filtering by capability` |
| `fix` | Bug fix | `fix(tasking): Handle null responder location` |
| `docs` | Documentation only | `docs(roadmap): Update Phase 0 completion status` |
| `style` | Code style (formatting, no logic change) | `style(gui): Format with black, fix flake8 warnings` |
| `refactor` | Code restructuring (no feature/fix) | `refactor(models): Extract base list model class` |
| `test` | Adding/updating tests | `test(analytics): Add telemetry summary tests` |
| `chore` | Build, tooling, dependencies | `chore(deps): Pin PySide6 to 6.6.0` |
| `perf` | Performance improvements | `perf(scheduler): Optimize scoring algorithm` |
| `ci` | CI/CD configuration | `ci(github): Add pytest workflow` |
| `revert` | Revert previous commit | `revert: Revert "feat(hq-gui): Add roster filtering"` |

### Scope Examples
- `hq-gui` - HQ Command GUI
- `fieldops` - FieldOps module
- `tasking` - Tasking engine
- `analytics` - Analytics module
- `qt-compat` - Qt compatibility layer
- `tests` - Test suite
- `docs` - Documentation
- `deps` - Dependencies

### Subject Guidelines
- Use imperative mood ("Add feature" not "Added feature")
- No period at the end
- Maximum 72 characters
- Capitalize first letter
- Be specific and descriptive

### Body Guidelines (Optional)
- Wrap at 72 characters
- Explain **what** and **why**, not **how**
- Reference related issues/PRs
- List breaking changes

### Footer Guidelines (Optional)
```
BREAKING CHANGE: <description>
Fixes: #123
Closes: #456
Refs: #789
Co-authored-by: Name <email>
```

### Examples

**Feature with body:**
```
feat(hq-gui): Add manual task assignment modal

Implement modal dialog for operators to manually assign units to tasks.
Includes unit selector with capability matching and scheduler score display.

Refs: #45
```

**Bug fix:**
```
fix(qt-compat): Handle PySide6 missing QtCore attribute

Gracefully fallback to shim mode when PySide6 is partially installed.
Prevents AttributeError during Qt binding validation.

Fixes: #78
```

**Documentation:**
```
docs(phase-0): Complete foundation audit documentation

Add comprehensive Phase 0 audit report covering all 10 sub-phases.
Documents environment validation, dependency management, and tooling setup.
```

**Breaking change:**
```
refactor(api): Change scheduler input format

BREAKING CHANGE: Task dictionary now requires 'id' field instead of 'task_id'.
Update all task creation code to use new format.

Refs: #92
```

---

## Code Style Guide

### Python Version
- **Minimum:** Python 3.9
- **Target:** Python 3.9+ features (no 3.10+ exclusive features yet)

### Formatting
- **Tool:** black (opinionated formatter)
- **Line Length:** 100 characters
- **Indentation:** 4 spaces (no tabs)
- **Quotes:** Double quotes for strings (black default)
- **Import Sorting:** isort (compatible with black)

### Naming Conventions
| Element | Convention | Example |
|---------|------------|---------|
| Module | snake_case | `tasking_engine.py` |
| Class | PascalCase | `TaskQueue`, `RosterListModel` |
| Function | snake_case | `calculate_score()`, `load_config()` |
| Variable | snake_case | `task_id`, `responder_list` |
| Constant | UPPER_CASE | `MAX_CAPACITY`, `DEFAULT_TIMEOUT` |
| Private | _leading_underscore | `_internal_method()` |
| Dunder | __double_underscore__ | `__init__()`, `__str__()` |

### Type Hints
- **Requirement:** All new code must have type hints
- **Style:** PEP 484 style
- **Tools:** mypy for static type checking

```python
from typing import List, Dict, Optional, Tuple

def assign_task(
    task_id: str,
    responder_id: str,
    priority: int = 1
) -> Optional[Dict[str, str]]:
    """Assign a task to a responder with optional priority."""
    ...
```

### Docstrings
- **Format:** Google style docstrings
- **Requirement:** All public functions, classes, modules

```python
def calculate_scheduling_score(
    task: Dict[str, Any],
    responder: Dict[str, Any]
) -> float:
    """Calculate scheduling score for task-responder pairing.

    Computes a score based on capability match, location proximity,
    and responder fatigue level. Higher scores indicate better matches.

    Args:
        task: Task dictionary with 'capabilities' and 'location' keys
        responder: Responder dictionary with 'capabilities', 'location',
                  'fatigue', and 'capacity' keys

    Returns:
        Scheduling score (0.0 to 100.0). Returns 0.0 if capability
        requirements are not met.

    Raises:
        KeyError: If required keys are missing from task or responder

    Example:
        >>> task = {"capabilities": ["medical"], "location": [0, 0]}
        >>> responder = {"capabilities": ["medical"], "location": [1, 1],
        ...              "fatigue": 20, "capacity": 2}
        >>> score = calculate_scheduling_score(task, responder)
        >>> print(f"Score: {score:.2f}")
        Score: 85.50
    """
    ...
```

### Import Organization
```python
# Standard library imports
import os
import sys
from typing import List, Dict

# Third-party imports
import yaml
from PySide6.QtCore import Qt, QAbstractListModel
from PySide6.QtWidgets import QMainWindow

# Local application imports
from hq_command.tasking_engine import TaskScheduler
from hq_command.analytics import summarize_telemetry
```

### Code Structure
- **Max Function Length:** 50 lines (guideline, not strict)
- **Max Complexity:** 10 (McCabe complexity)
- **Max Arguments:** 7 per function
- **Max Nesting:** 4 levels

### Error Handling
```python
# Specific exceptions, not bare except
try:
    result = load_config(path)
except FileNotFoundError:
    logger.error(f"Config file not found: {path}")
    raise
except yaml.YAMLError as e:
    logger.error(f"Invalid YAML in config: {e}")
    return default_config()
```

### Logging
```python
import logging

logger = logging.getLogger(__name__)

# Use appropriate log levels
logger.debug("Detailed diagnostic information")
logger.info("General informational message")
logger.warning("Warning: potential issue detected")
logger.error("Error: operation failed")
logger.critical("Critical: system unusable")
```

---

## Documentation Standards

### Code Documentation
- **Docstrings:** All public APIs (modules, classes, functions)
- **Inline Comments:** For complex logic only (code should be self-documenting)
- **TODOs:** Use `# TODO: description` for future improvements

### Markdown Documentation
- **Format:** GitHub Flavored Markdown (GFM)
- **Line Length:** 120 characters (documentation only)
- **Headers:** ATX style (`# ## ###`)
- **Code Blocks:** Fenced with language specifiers

```markdown
# Main Header

## Subheader

### Sub-subheader

**Bold text** and *italic text*

- Bullet list
- Second item

1. Numbered list
2. Second item

```python
# Code block with syntax highlighting
def example():
    pass
\```

[Link text](url)
![Image alt text](image-url)
```

### Documentation Structure
```
docs/
├── phase_0_audit.md              # Phase 0 completion audit
├── development_standards.md      # This document
├── hq_command_gui_roadmap.md     # Phase 0-9 roadmap
├── hq_command_gui_design.md      # UI/UX specifications
├── fieldops_gui_style.md         # Design tokens
└── api/                          # Future: API documentation
    └── hq_command.md
```

---

## Testing Requirements

### Test Coverage
- **Minimum:** 80% line coverage
- **Target:** 90%+ for new code
- **Tools:** pytest, pytest-cov

### Test Organization
```
tests/
├── conftest.py                   # Shared fixtures
├── hq_command/
│   ├── test_analytics.py         # Unit tests
│   ├── test_tasking_engine.py
│   └── test_gui_controller.py
└── integration/                  # Future: integration tests
    └── test_full_workflow.py
```

### Test Naming
```python
def test_<function>_<scenario>_<expected_result>():
    """Test that function behaves correctly in scenario."""
    ...

# Examples:
def test_calculate_score_matching_capabilities_returns_high_score():
def test_assign_task_invalid_id_raises_key_error():
def test_load_config_missing_file_returns_default():
```

### Test Structure (Arrange-Act-Assert)
```python
def test_assign_task_updates_responder_capacity():
    # Arrange: Set up test data
    task = {"id": "t1", "capabilities": ["medical"]}
    responder = {"id": "r1", "capacity": 2, "assigned": []}

    # Act: Execute the function under test
    result = assign_task(task, responder)

    # Assert: Verify expected outcomes
    assert result is True
    assert len(responder["assigned"]) == 1
    assert responder["assigned"][0] == "t1"
```

### Running Tests
```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html --cov-report=term

# Run specific test file
pytest tests/hq_command/test_analytics.py

# Run with verbose output
pytest -v -s

# Run tests matching pattern
pytest -k "test_calculate_score"
```

---

## Review Process

### Pull Request Requirements
1. **Branch:** Feature branch from `main` or `dev`
2. **Description:** Clear explanation of changes
3. **Tests:** All tests pass, coverage maintained/improved
4. **Linting:** flake8, pylint, mypy pass
5. **Documentation:** Updated if needed
6. **Commits:** Follow commit message standards
7. **Review:** At least 1 approval required

### PR Description Template
```markdown
## Summary
Brief description of changes (1-2 sentences)

## Changes
- Bullet list of specific changes
- Include file paths if helpful

## Testing
- Describe how changes were tested
- List new test cases added

## Related Issues
Fixes: #123
Refs: #456

## Checklist
- [ ] Tests added/updated
- [ ] Documentation updated
- [ ] Linting passes (flake8, pylint, mypy)
- [ ] All tests pass
- [ ] No breaking changes (or documented)
```

### Review Guidelines
**Reviewers should check:**
- Code correctness and logic
- Test coverage and quality
- Documentation clarity
- Security implications
- Performance considerations
- Code style compliance
- Error handling
- Edge cases

**Review etiquette:**
- Be respectful and constructive
- Suggest improvements, don't demand
- Explain reasoning for requested changes
- Approve when requirements are met

---

## Security Guidelines

### Input Validation
- Validate all user inputs
- Use type hints and runtime validation
- Sanitize strings used in commands or queries

### Secrets Management
- **NEVER** commit secrets, keys, credentials
- Use environment variables or secret management
- Add sensitive files to `.gitignore`

```python
# Good: Load from environment
import os
api_key = os.environ.get("PRRC_API_KEY")

# Bad: Hardcoded secret
api_key = "sk-1234567890abcdef"  # NEVER DO THIS
```

### Dependencies
- Pin versions in `requirements.txt`
- Run `safety check` weekly for vulnerabilities
- Update dependencies regularly
- Review dependency licenses

### Data Protection
- Encrypt sensitive data at rest
- Use TLS for network communication
- Implement proper access controls
- Log security events

### Vulnerability Reporting
- Report security issues privately to maintainers
- Do not create public issues for vulnerabilities
- Follow responsible disclosure practices

---

## Pre-commit Checklist

Before committing:
- [ ] Code formatted with `black src/ tests/`
- [ ] Imports sorted with `isort src/ tests/`
- [ ] Linting passes: `flake8 src/` and `pylint src/`
- [ ] Type checking passes: `mypy src/`
- [ ] Tests pass: `pytest`
- [ ] Coverage maintained: `pytest --cov=src`
- [ ] Documentation updated if needed
- [ ] Commit message follows standards

---

## Tools Quick Reference

```bash
# Setup development environment
pip install -r requirements-dev.txt

# Format code
black src/ tests/
isort src/ tests/

# Lint code
flake8 src/
pylint src/
ruff check src/

# Type check
mypy src/

# Run tests
pytest
pytest --cov=src --cov-report=html

# Security scan
bandit -r src/
safety check

# Build package
python -m build
```

---

## Additional Resources

- [PEP 8 - Style Guide for Python Code](https://peps.python.org/pep-0008/)
- [PEP 484 - Type Hints](https://peps.python.org/pep-0484/)
- [PEP 257 - Docstring Conventions](https://peps.python.org/pep-0257/)
- [Conventional Commits](https://www.conventionalcommits.org/)
- [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html)
- [Black Code Style](https://black.readthedocs.io/)
- [pytest Documentation](https://docs.pytest.org/)

---

**Document Version:** 1.0.0
**Last Updated:** 2025-11-02
**Status:** Active
**Review Schedule:** Quarterly
