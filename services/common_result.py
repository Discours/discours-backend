from dataclasses import dataclass
from typing import Any

from graphql.error import GraphQLError

from auth.orm import Author
from orm.community import Community
from orm.draft import Draft
from orm.reaction import Reaction
from orm.shout import Shout
from orm.topic import Topic
from utils.logger import root_logger as logger


def handle_error(operation: str, error: Exception) -> GraphQLError:
    """Обрабатывает ошибки в резолверах"""
    logger.error(f"Ошибка при {operation}: {error}")
    return GraphQLError(f"Не удалось {operation}: {error}")


@dataclass
class CommonResult:
    """Общий результат для GraphQL запросов"""

    error: str | None = None
    drafts: list[Draft] | None = None  # Draft objects
    draft: Draft | None = None  # Draft object
    slugs: list[str] | None = None
    shout: Shout | None = None
    shouts: list[Shout] | None = None
    author: Author | None = None
    authors: list[Author] | None = None
    reaction: Reaction | None = None
    reactions: list[Reaction] | None = None
    topic: Topic | None = None
    topics: list[Topic] | None = None
    community: Community | None = None
    communities: list[Community] | None = None


@dataclass
class AuthorFollowsResult:
    """Результат для get_author_follows запроса"""

    topics: list[Any] | None = None  # Topic dicts
    authors: list[Any] | None = None  # Author dicts
    communities: list[Any] | None = None  # Community dicts
    error: str | None = None
