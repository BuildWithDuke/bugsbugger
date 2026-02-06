# Contributing to BugsBugger

Thanks for your interest in contributing! 🐛

## Getting Started

1. Fork the repository
2. Clone your fork: `git clone https://github.com/YOUR_USERNAME/bugsbugger.git`
3. Create a branch: `git checkout -b feature/your-feature`
4. Make your changes
5. Test thoroughly
6. Commit with clear messages
7. Push and create a PR

## Development Setup

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Check coverage
pytest --cov=bugsbugger tests/

# Lint
ruff check .
ruff format .
```

## Code Style

- Follow PEP 8
- Use type hints
- Write docstrings for functions
- Keep functions focused and small
- Test your changes

## Testing

Please add tests for new features:
- Unit tests in `tests/`
- Integration tests for end-to-end flows
- Test edge cases

## Pull Request Guidelines

- One feature per PR
- Update README if needed
- Add tests
- Ensure all tests pass
- Keep commits clean and atomic

## Areas to Contribute

- 🐛 Bug fixes
- ✨ New features
- 📚 Documentation improvements
- 🧪 More tests
- 🎨 UI/UX improvements
- 🌍 Internationalization

## Questions?

Open an issue or start a discussion!
