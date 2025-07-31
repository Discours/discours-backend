from collections.abc import Collection
from typing import Any, Union

import orjson

from orm.notification import Notification
from orm.reaction import Reaction
from orm.shout import Shout
from services.db import local_session
from services.redis import redis
from utils.logger import root_logger as logger


def save_notification(action: str, entity: str, payload: Union[dict[Any, Any], str, int, None]) -> None:
    """Save notification with proper payload handling"""
    if payload is None:
        return

    if isinstance(payload, (Reaction, Shout)):
        # Convert ORM objects to dict representation
        payload = {"id": payload.id}

    with local_session() as session:
        n = Notification(action=action, entity=entity, payload=payload)
        session.add(n)
        session.commit()


async def notify_reaction(reaction: Union[Reaction, int], action: str = "create") -> None:
    channel_name = "reaction"

    # Преобразуем объект Reaction в словарь для сериализации
    if isinstance(reaction, Reaction):
        reaction_payload = {
            "id": reaction.id,
            "kind": reaction.kind,
            "body": reaction.body,
            "shout": reaction.shout,
            "created_by": reaction.created_by,
            "created_at": getattr(reaction, "created_at", None),
        }
    else:
        # Если передан просто ID
        reaction_payload = {"id": reaction}

    data = {"payload": reaction_payload, "action": action}
    try:
        save_notification(action, channel_name, reaction_payload)
        await redis.publish(channel_name, orjson.dumps(data))
    except (ConnectionError, TimeoutError, ValueError) as e:
        logger.error(f"Failed to publish to channel {channel_name}: {e}")


async def notify_shout(shout: dict[str, Any], action: str = "update") -> None:
    channel_name = "shout"
    data = {"payload": shout, "action": action}
    try:
        payload = data.get("payload")
        if isinstance(payload, Collection) and not isinstance(payload, (str, bytes, dict)):
            payload = str(payload)
        save_notification(action, channel_name, payload)
        await redis.publish(channel_name, orjson.dumps(data))
    except (ConnectionError, TimeoutError, ValueError) as e:
        logger.error(f"Failed to publish to channel {channel_name}: {e}")


async def notify_follower(follower: dict[str, Any], author_id: int, action: str = "follow") -> None:
    channel_name = f"follower:{author_id}"
    try:
        # Simplify dictionary before publishing
        simplified_follower = {k: follower[k] for k in ["id", "name", "slug", "pic"]}
        data = {"payload": simplified_follower, "action": action}
        # save in channel
        payload = data.get("payload")
        if isinstance(payload, Collection) and not isinstance(payload, (str, bytes, dict)):
            payload = str(payload)
        save_notification(action, channel_name, payload)

        # Convert data to JSON string
        json_data = orjson.dumps(data)

        # Ensure the data is not empty before publishing
        if json_data:
            # Use the 'await' keyword when publishing
            await redis.publish(channel_name, json_data)

    except (ConnectionError, TimeoutError, KeyError, ValueError) as e:
        # Log the error and re-raise it
        logger.error(f"Failed to publish to channel {channel_name}: {e}")


async def notify_draft(draft_data: dict[str, Any], action: str = "publish") -> None:
    """
    Отправляет уведомление о публикации или обновлении черновика.

    Функция гарантирует, что данные черновика сериализуются корректно, включая
    связанные атрибуты (topics, authors).

    Args:
        draft_data: Словарь с данными черновика или ORM объект. Должен содержать минимум id и title
        action: Действие ("publish", "update"). По умолчанию "publish"

    Returns:
        None

    Examples:
        >>> draft = {"id": 1, "title": "Тестовый черновик", "slug": "test-draft"}
        >>> await notify_draft(draft, "publish")
    """
    channel_name = "draft"
    try:
        # Убеждаемся, что все необходимые данные присутствуют
        # и объект не требует доступа к отсоединенным атрибутам
        if isinstance(draft_data, dict):
            draft_payload = draft_data
        else:
            # Если это ORM объект, преобразуем его в словарь с нужными атрибутами
            draft_payload = {
                "id": getattr(draft_data, "id", None),
                "slug": getattr(draft_data, "slug", None),
                "title": getattr(draft_data, "title", None),
                "subtitle": getattr(draft_data, "subtitle", None),
                "media": getattr(draft_data, "media", None),
                "created_at": getattr(draft_data, "created_at", None),
                "updated_at": getattr(draft_data, "updated_at", None),
            }

            # Если переданы связанные атрибуты, добавим их
            if hasattr(draft_data, "topics") and draft_data.topics is not None:
                draft_payload["topics"] = [{"id": t.id, "name": t.name, "slug": t.slug} for t in draft_data.topics]

            if hasattr(draft_data, "authors") and draft_data.authors is not None:
                draft_payload["authors"] = [
                    {
                        "id": a.id,
                        "name": a.name,
                        "slug": a.slug,
                        "pic": getattr(a, "pic", None),
                    }
                    for a in draft_data.authors
                ]

        data = {"payload": draft_payload, "action": action}

        # Сохраняем уведомление
        payload = data.get("payload")
        if isinstance(payload, Collection) and not isinstance(payload, (str, bytes, dict)):
            payload = str(payload)
        save_notification(action, channel_name, payload)

        # Публикуем в Redis
        json_data = orjson.dumps(data)
        if json_data:
            await redis.publish(channel_name, json_data)

    except (ConnectionError, TimeoutError, AttributeError, ValueError) as e:
        logger.error(f"Failed to publish to channel {channel_name}: {e}")
