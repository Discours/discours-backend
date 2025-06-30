# GraphQL API Backend

<div align="center">

![Version](https://img.shields.io/badge/v0.5.5-lightgrey)
![Python](https://img.shields.io/badge/python%203.12+-gold?logo=python&logoColor=black)
![GraphQL](https://img.shields.io/badge/graphql%20api-pink?logo=graphql&logoColor=black)
![Tests](https://img.shields.io/badge/tests%2085%25-lightcyan?logo=pytest&logoColor=black)

![PostgreSQL](https://img.shields.io/badge/postgresql-lightblue?logo=postgresql&logoColor=black)
![Redis](https://img.shields.io/badge/redis-salmon?logo=redis&logoColor=black)
![txtai](https://img.shields.io/badge/txtai-lavender?logo=elasticsearch&logoColor=black)

</div>

Backend service providing GraphQL API for content management system with reactions, ratings and topics.

## 📚 Documentation

![API](https://img.shields.io/badge/api-docs-lightblue?logo=swagger&logoColor=black) • [API Documentation](docs/api.md)
![Auth](https://img.shields.io/badge/auth-guide-lightcyan?logo=key&logoColor=black) • [Authentication Guide](docs/auth.md)
![Cache](https://img.shields.io/badge/redis-schema-salmon?logo=redis&logoColor=black) • [Caching System](docs/redis-schema.md)
![Features](https://img.shields.io/badge/features-overview-lavender?logo=list&logoColor=black) • [Features Overview](docs/features.md)

## 🚀 Core Features

### Shouts (Posts)
- CRUD operations via GraphQL mutations
- Rich filtering and sorting options
- Support for multiple authors and topics
- Rating system with likes/dislikes
- Comments and nested replies
- Bookmarks and following

### Reactions System
- `ReactionKind` types: LIKE, DISLIKE, COMMENT
- Rating calculation for shouts and comments
- User-specific reaction tracking
- Reaction stats and aggregations
- Nested comments support

### Authors & Topics
- Author profiles with stats
- Topic categorization and hierarchy
- Following system for authors/topics
- Activity tracking and stats
- Community features

## 🛠️ Tech Stack

**Core:** Python 3.12 • GraphQL • PostgreSQL • SQLAlchemy • JWT • Redis • txtai
**Server:** Starlette • Granian • Nginx
**Tools:** Pytest • MyPy • Ruff
**Deploy:** Dokku • Gitea • Glitchtip

## 🔧 Development

![PRs Welcome](https://img.shields.io/badge/PRs-welcome-lightcyan?logo=git&logoColor=black)
![Ruff](https://img.shields.io/badge/ruff-gold?logo=ruff&logoColor=black)
![Mypy](https://img.shields.io/badge/mypy-lavender?logo=python&logoColor=black)

### 📦 Prepare environment:

```shell
python3.12 -m venv venv
source venv/bin/activate
pip install -r requirements.dev.txt
```

### 🚀 Run server

First, certificates are required to run the server with HTTPS.

```shell
mkcert -install
mkcert localhost
```

Then, run the server:

```shell
python -m granian main:app --interface asgi
```

### ⚡ Useful Commands

```shell
# Linting and import sorting
ruff check . --fix --select I

# Code formatting
ruff format . --line-length=120

# Run tests
pytest

# Type checking
mypy .

# dev run
python -m granian main:app --interface asgi
```

### 📝 Code Style

![Line 120](https://img.shields.io/badge/line%20120-lightblue?logo=prettier&logoColor=black)
![Types](https://img.shields.io/badge/typed-pink?logo=python&logoColor=black)
![Docs](https://img.shields.io/badge/documented-lightcyan?logo=markdown&logoColor=black)

**Ruff** for linting • **120 char** lines • **Type hints** required • **Docstrings** for public methods

### 🔍 GraphQL Development

Test queries in GraphQL Playground at `http://localhost:8000`:

```graphql
# Example query
query GetShout($slug: String) {
  get_shout(slug: $slug) {
    id
    title
    main_author {
      name
    }
  }
}
```

---

## 📊 Project Stats

<div align="center">

![Lines](https://img.shields.io/badge/15k%2B-lines-lightcyan?logo=code&logoColor=black)
![Files](https://img.shields.io/badge/100%2B-files-lavender?logo=folder&logoColor=black)
![Coverage](https://img.shields.io/badge/85%25-coverage-gold?logo=test-tube&logoColor=black)
![MIT](https://img.shields.io/badge/MIT-license-silver?logo=balance-scale&logoColor=black)

</div>

## 🤝 Contributing

![Contributing](https://img.shields.io/badge/contributing-guide-salmon?logo=handshake&logoColor=black) • [Read the guide](CONTRIBUTING.md)

We welcome contributions! Please read our contributing guide before submitting PRs.

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🔗 Links

![Website](https://img.shields.io/badge/discours.io-website-lightblue?logo=globe&logoColor=black) • [discours.io](https://discours.io)
![GitHub](https://img.shields.io/badge/discours/core-github-silver?logo=github&logoColor=black) • [Source Code](https://github.com/discours/core)

---

<div align="center">

**Made with ❤️ by the Discours Team**

![Made with Love](https://img.shields.io/badge/made%20with%20❤️-pink?logo=heart&logoColor=black)
![Open Source](https://img.shields.io/badge/open%20source-lightcyan?logo=open-source-initiative&logoColor=black)

</div>
