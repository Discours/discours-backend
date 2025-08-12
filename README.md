# Discours Core

Core backend for Discours.io platform

## Requirements

- Python 3.11+
- uv (Python package manager)

## Installation

### Install uv

```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

### Setup project

```bash
# Clone repository
git clone <repository-url>
cd discours-core

# Install dependencies
uv sync --dev

# Activate virtual environment
source .venv/bin/activate  # Linux/macOS
# or
.venv\Scripts\activate     # Windows
```

## Development

### Install dependencies

```bash
# Install all dependencies (including dev)
uv sync --dev

# Install only production dependencies
uv sync

# Install specific group
uv sync --group test
uv sync --group lint
```

### Run tests

```bash
# Run all tests
uv run pytest

# Run specific test file
uv run pytest tests/test_auth_fixes.py

# Run with coverage
uv run pytest --cov=services,utils,orm,resolvers
```

### Code quality

```bash
# Run ruff linter
uv run ruff check .

# Run ruff formatter
uv run ruff format .

# Run mypy type checker
uv run mypy .
```

### Run application

```bash
# Run main application
uv run python main.py

# Run development server
uv run python dev.py
```

## Project structure

```
discours-core/
├── auth/           # Authentication and authorization
├── cache/          # Caching system
├── orm/            # Database models
├── resolvers/      # GraphQL resolvers
├── services/       # Business logic services
├── utils/          # Utility functions
├── schema/         # GraphQL schema
├── tests/          # Test suite
└── docs/           # Documentation
```

## Configuration

The project uses `pyproject.toml` for configuration:

- **Dependencies**: Defined in `[project.dependencies]` and `[project.optional-dependencies]`
- **Build system**: Uses `hatchling` for building packages
- **Code quality**: Configured with `ruff` and `mypy`
- **Testing**: Configured with `pytest`

## CI/CD

The project includes GitHub Actions workflows for:

- Automated testing
- Code quality checks
- Deployment to staging and production servers

## License

MIT License
