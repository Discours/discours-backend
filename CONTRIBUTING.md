# Contributing to Discours Core

🎉 Thanks for taking the time to contribute!

## 🚀 Quick Start

1. Fork the repository
2. Create a feature branch: `git checkout -b my-new-feature`
3. Make your changes
4. Add tests for your changes
5. Run the test suite: `pytest`
6. Run the linter: `ruff check . --fix && ruff format . --line-length=120`
7. Commit your changes: `git commit -am 'Add some feature'`
8. Push to the branch: `git push origin my-new-feature`
9. Create a Pull Request

## 📋 Development Guidelines

### Code Style

- **Python 3.12+** required
- **Line length**: 120 characters max
- **Type hints**: Required for all functions
- **Docstrings**: Required for public methods
- **Ruff**: For linting and formatting

### Testing

- **Pytest** for testing
- **85%+ coverage** required
- Test both positive and negative cases
- Mock external dependencies

### Commit Messages

We follow [Conventional Commits](https://conventionalcommits.org/):

```
feat: add user authentication
fix: resolve database connection issue
docs: update API documentation
test: add tests for reaction system
refactor: improve GraphQL resolvers
```

### Python Code Standards

```python
# Good example
async def create_reaction(
    session: Session,
    author_id: int,
    reaction_data: dict[str, Any]
) -> dict[str, Any]:
    """
    Create a new reaction.

    Args:
        session: Database session
        author_id: ID of the author creating the reaction
        reaction_data: Reaction data

    Returns:
        Created reaction data

    Raises:
        ValueError: If reaction data is invalid
    """
    if not reaction_data.get("kind"):
        raise ValueError("Reaction kind is required")

    reaction = Reaction(**reaction_data)
    session.add(reaction)
    session.commit()

    return reaction.dict()
```

## 🐛 Bug Reports

When filing a bug report, please include:

- **Python version**
- **Package versions** (`pip freeze`)
- **Error message** and full traceback
- **Steps to reproduce**
- **Expected vs actual behavior**

## 💡 Feature Requests

For feature requests, please include:

- **Use case** description
- **Proposed solution**
- **Alternatives considered**
- **Breaking changes** (if any)

## 📚 Documentation

- Update documentation for new features
- Add examples for complex functionality
- Use Russian comments for Russian-speaking team members
- Keep README.md up to date

## 🔍 Code Review Process

1. **Automated checks** must pass (tests, linting)
2. **Manual review** by at least one maintainer
3. **Documentation** must be updated if needed
4. **Breaking changes** require discussion

## 🏷️ Release Process

We follow [Semantic Versioning](https://semver.org/):

- **MAJOR**: Breaking changes
- **MINOR**: New features (backward compatible)
- **PATCH**: Bug fixes (backward compatible)

## 🤝 Community

- Be respectful and inclusive
- Help newcomers get started
- Share knowledge and best practices
- Follow our [Code of Conduct](CODE_OF_CONDUCT.md)

## 📞 Getting Help

- **Issues**: For bugs and feature requests
- **Discussions**: For questions and general discussion
- **Documentation**: Check `docs/` folder first

Thank you for contributing! 🙏
