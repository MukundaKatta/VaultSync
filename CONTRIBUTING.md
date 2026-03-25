# Contributing to VaultSync

Thank you for your interest in contributing to VaultSync! This document provides guidelines and instructions for contributing.

## Getting Started

1. **Fork and clone** the repository:
   ```bash
   git clone https://github.com/officethree/VaultSync.git
   cd VaultSync
   ```

2. **Install development dependencies**:
   ```bash
   make dev
   ```

3. **Create a feature branch**:
   ```bash
   git checkout -b feature/my-feature
   ```

## Development Workflow

### Running Tests

```bash
make test
```

### Linting and Type Checking

```bash
make lint
make typecheck
```

### Formatting

```bash
make format
```

## Code Style

- We use **ruff** for linting and formatting.
- We use **mypy** in strict mode for type checking.
- All public functions and classes must have docstrings.
- Target Python 3.10+ and use modern type hints (e.g., `str | None` instead of `Optional[str]`).

## Pull Request Process

1. Ensure all tests pass and there are no lint or type errors.
2. Update documentation if you change public APIs.
3. Add tests for new functionality.
4. Write a clear PR description explaining the change.

## Reporting Issues

- Use GitHub Issues to report bugs or request features.
- Include reproduction steps, expected behavior, and actual behavior.

## Code of Conduct

Be respectful, constructive, and inclusive. We are all here to build great software together.

---

**Built by Officethree Technologies | Made with love and AI**
