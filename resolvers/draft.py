import time
from typing import Any

from graphql import GraphQLResolveInfo
from sqlalchemy.orm import Session, joinedload

from auth.orm import Author
from cache.cache import (
    invalidate_shout_related_cache,
    invalidate_shouts_cache,
)
from orm.draft import Draft, DraftAuthor, DraftTopic
from orm.shout import Shout, ShoutAuthor, ShoutTopic
from services.auth import login_required
from services.db import local_session
from services.notify import notify_shout
from services.schema import mutation, query
from services.search import search_service
from utils.extract_text import extract_text
from utils.logger import root_logger as logger


def create_shout_from_draft(session: Session | None, draft: Draft, author_id: int) -> Shout:
    """
    Создаёт новый объект публикации (Shout) на основе черновика.

    Args:
        session: SQLAlchemy сессия (не используется, для совместимости)
        draft (Draft): Объект черновика
        author_id (int): ID автора публикации

    Returns:
        Shout: Новый объект публикации (не сохранённый в базе)

    Пример:
        >>> from orm.draft import Draft
        >>> draft = Draft(id=1, title='Заголовок', body='Текст', slug='slug', created_by=1)
        >>> shout = create_shout_from_draft(None, draft, 1)
        >>> shout.title
        'Заголовок'
        >>> shout.body
        'Текст'
        >>> shout.created_by
        1
    """
    # Создаем новую публикацию
    shout = Shout(
        body=draft.body or "",
        slug=draft.slug,
        cover=draft.cover,
        cover_caption=draft.cover_caption,
        lead=draft.lead,
        title=draft.title or "",
        subtitle=draft.subtitle,
        layout=draft.layout or "article",
        media=draft.media or [],
        lang=draft.lang or "ru",
        seo=draft.seo,
        created_by=author_id,
        community=draft.community,
        draft=draft.id,
        deleted_at=None,
    )

    # Инициализируем пустые массивы для связей
    shout.topics = []
    shout.authors = []

    return shout


@query.field("load_drafts")
@login_required
async def load_drafts(_: None, info: GraphQLResolveInfo) -> dict[str, Any]:
    """
    Загружает все черновики, доступные текущему пользователю.

    Предварительно загружает связанные объекты (topics, authors),
    чтобы избежать ошибок с отсоединенными объектами при сериализации.

    Returns:
        dict: Список черновиков или сообщение об ошибке
    """
    author_dict = info.context.get("author") or {}
    author_id = author_dict.get("id")

    if not author_id:
        return {"error": "Author ID is required"}

    try:
        with local_session() as session:
            # Предзагружаем authors и topics
            drafts_query = (
                session.query(Draft)
                .options(
                    joinedload(Draft.topics),
                    joinedload(Draft.authors),
                )
                .where(Draft.authors.any(Author.id == author_id))
            )
            drafts = drafts_query.all()

            # Преобразуем объекты в словари, пока они в контексте сессии
            drafts_data = []
            for draft in drafts:
                draft_dict = draft.dict()
                # Всегда возвращаем массив для topics, даже если он пустой
                draft_dict["topics"] = [topic.dict() for topic in (draft.topics or [])]
                draft_dict["authors"] = [author.dict() for author in (draft.authors or [])]
                drafts_data.append(draft_dict)

            return {"drafts": drafts_data}
    except Exception as e:
        logger.error(f"Failed to load drafts: {e}", exc_info=True)
        return {"error": f"Failed to load drafts: {e!s}"}


@mutation.field("create_draft")
@login_required
async def create_draft(_: None, info: GraphQLResolveInfo, draft_input: dict[str, Any]) -> dict[str, Any]:
    """Create a new draft.

    Args:
        info: GraphQL context
        draft_input (dict): Draft data including optional fields:
            - title (str, required) - заголовок черновика
            - body (str, required) - текст черновика
            - slug (str)
            - etc.

    Returns:
        dict: Contains either:
            - draft: The created draft object
            - error: Error message if creation failed

    Example:
        >>> async def test_create():
        ...     context = {'user_id': '123', 'author': {'id': 1}}
        ...     info = type('Info', (), {'context': context})()
        ...     result = await create_draft(None, info, {'title': 'Test'})
        ...     assert result.get('error') is None
        ...     assert result['draft'].title == 'Test'
        ...     return result
    """
    author_dict = info.context.get("author") or {}
    author_id = author_dict.get("id")

    if not author_id or not isinstance(author_id, int):
        return {"error": "Author ID is required"}

    # Проверяем обязательные поля
    if "body" not in draft_input or not draft_input["body"]:
        draft_input["body"] = ""  # Пустая строка вместо NULL

    if "title" not in draft_input or not draft_input["title"]:
        draft_input["title"] = ""  # Пустая строка вместо NULL

    # Проверяем slug - он должен быть или не пустым, или не передаваться вообще
    if "slug" in draft_input and (draft_input["slug"] is None or draft_input["slug"] == ""):
        # При создании черновика удаляем пустой slug из входных данных
        del draft_input["slug"]

    try:
        with local_session() as session:
            # Remove id from input if present since it's auto-generated
            draft_input.pop("id", None)

            # Добавляем текущее время создания и ID автора
            draft_input["created_at"] = int(time.time())
            draft_input["created_by"] = author_id

            # Исключаем поле shout из создания draft (оно добавляется только при публикации)
            draft_input.pop("shout", None)

            # Создаем draft вручную, исключая проблемные поля
            draft = Draft()
            draft.created_at = draft_input["created_at"]
            draft.created_by = draft_input["created_by"]
            draft.community = draft_input.get("community", 1)
            draft.layout = draft_input.get("layout", "article")
            draft.title = draft_input.get("title", "")
            draft.body = draft_input.get("body", "")
            draft.lang = draft_input.get("lang", "ru")

            # Опциональные поля
            if "slug" in draft_input:
                draft.slug = draft_input["slug"]
            if "subtitle" in draft_input:
                draft.subtitle = draft_input["subtitle"]
            if "lead" in draft_input:
                draft.lead = draft_input["lead"]
            if "cover" in draft_input:
                draft.cover = draft_input["cover"]
            if "cover_caption" in draft_input:
                draft.cover_caption = draft_input["cover_caption"]
            if "seo" in draft_input:
                draft.seo = draft_input["seo"]
            if "media" in draft_input:
                draft.media = draft_input["media"]

            session.add(draft)
            session.flush()

            # Добавляем создателя как автора
            da = DraftAuthor(draft=draft.id, author=author_id)
            session.add(da)

            session.commit()
            return {"draft": draft}
    except Exception as e:
        logger.error(f"Failed to create draft: {e}", exc_info=True)
        return {"error": f"Failed to create draft: {e!s}"}


def generate_teaser(body: str, limit: int = 300) -> str:
    body_text = extract_text(body)
    return ". ".join(body_text[:limit].split(". ")[:-1])


@mutation.field("update_draft")
@login_required
async def update_draft(_: None, info: GraphQLResolveInfo, draft_id: int, draft_input: dict[str, Any]) -> dict[str, Any]:
    """Обновляет черновик публикации.

    Args:
        draft_id: ID черновика для обновления
        draft_input: Данные для обновления черновика согласно схеме DraftInput:
            - layout: String
            - author_ids: [Int!]
            - topic_ids: [Int!]
            - main_topic_id: Int
            - media: [MediaItemInput]
            - lead: String
            - subtitle: String
            - lang: String
            - seo: String
            - body: String
            - title: String
            - slug: String
            - cover: String
            - cover_caption: String

    Returns:
        dict: Обновленный черновик или сообщение об ошибке
    """
    author_dict = info.context.get("author") or {}
    author_id = author_dict.get("id")

    if not author_id or not isinstance(author_id, int):
        return {"error": "Author ID is required"}

    try:
        with local_session() as session:
            draft = session.query(Draft).where(Draft.id == draft_id).first()
            if not draft:
                return {"error": "Draft not found"}

            # Фильтруем входные данные, оставляя только разрешенные поля
            allowed_fields = {
                "layout",
                "author_ids",
                "topic_ids",
                "main_topic_id",
                "media",
                "lead",
                "subtitle",
                "lang",
                "seo",
                "body",
                "title",
                "slug",
                "cover",
                "cover_caption",
            }
            filtered_input = {k: v for k, v in draft_input.items() if k in allowed_fields}

            # Проверяем slug
            if "slug" in filtered_input and not filtered_input["slug"]:
                del filtered_input["slug"]

            # Обновляем связи с авторами если переданы
            if "author_ids" in filtered_input:
                author_ids = filtered_input.pop("author_ids")
                if author_ids:
                    # Очищаем текущие связи
                    session.query(DraftAuthor).where(DraftAuthor.draft == draft_id).delete()
                    # Добавляем новые связи
                    for aid in author_ids:
                        da = DraftAuthor(draft=draft_id, author=aid)
                        session.add(da)

            # Обновляем связи с темами если переданы
            if "topic_ids" in filtered_input:
                topic_ids = filtered_input.pop("topic_ids")
                main_topic_id = filtered_input.pop("main_topic_id", None)
                if topic_ids:
                    # Очищаем текущие связи
                    session.query(DraftTopic).where(DraftTopic.draft == draft_id).delete()
                    # Добавляем новые связи
                    for tid in topic_ids:
                        dt = DraftTopic(
                            draft=draft_id,
                            topic=tid,
                            main=(tid == main_topic_id) if main_topic_id else False,
                        )
                        session.add(dt)

            # Генерируем SEO если не предоставлено
            if "seo" not in filtered_input and not draft.seo:
                body_src = filtered_input.get("body", draft.body)
                lead_src = filtered_input.get("lead", draft.lead)

                try:
                    body_text = extract_text(body_src) if body_src else None
                    lead_text = extract_text(lead_src) if lead_src else None
                    body_teaser = generate_teaser(body_text, 300) if body_text else ""
                    filtered_input["seo"] = lead_text if lead_text else body_teaser
                except Exception as e:
                    logger.warning(f"Failed to generate SEO for draft {draft_id}: {e}")

            # Обновляем основные поля черновика
            for key, value in filtered_input.items():
                setattr(draft, key, value)

            # Обновляем метаданные
            draft.updated_at = int(time.time())  # type: ignore[assignment]
            draft.updated_by = author_id  # type: ignore[assignment]

            session.commit()

            # Преобразуем объект в словарь для ответа
            draft_dict = draft.dict()
            draft_dict["topics"] = [topic.dict() for topic in draft.topics]
            draft_dict["authors"] = [author.dict() for author in draft.authors]
            # Добавляем объект автора в updated_by
            draft_dict["updated_by"] = author_dict

            return {"draft": draft_dict}

    except Exception as e:
        logger.error(f"Failed to update draft: {e}", exc_info=True)
        return {"error": f"Failed to update draft: {e!s}"}


@mutation.field("delete_draft")
@login_required
async def delete_draft(_: None, info: GraphQLResolveInfo, draft_id: int) -> dict[str, Any]:
    author_dict = info.context.get("author") or {}
    author_id = author_dict.get("id")

    with local_session() as session:
        draft = session.query(Draft).where(Draft.id == draft_id).first()
        if not draft:
            return {"error": "Draft not found"}
        if author_id != draft.created_by and draft.authors.where(Author.id == author_id).count() == 0:
            return {"error": "You are not allowed to delete this draft"}
        session.delete(draft)
        session.commit()
        return {"draft": draft}


def validate_html_content(html_content: str) -> tuple[bool, str]:
    """
    Проверяет валидность HTML контента через trafilatura.

    Args:
        html_content: HTML строка для проверки

    Returns:
        tuple[bool, str]: (валидность, сообщение об ошибке)

    Example:
        >>> is_valid, error = validate_html_content("<p>Valid HTML</p>")
        >>> is_valid
        True
        >>> error
        ''
        >>> is_valid, error = validate_html_content("Invalid < HTML")
        >>> is_valid
        False
        >>> 'Invalid HTML' in error
        True
    """
    if not html_content or not html_content.strip():
        return False, "Content is empty"

    try:
        extracted = extract_text(html_content)
        return bool(extracted), extracted or ""
    except Exception as e:
        logger.error(f"HTML validation error: {e}", exc_info=True)
        return False, f"Invalid HTML content: {e!s}"


@mutation.field("publish_draft")
@login_required
async def publish_draft(_: None, info: GraphQLResolveInfo, draft_id: int) -> dict[str, Any]:
    """
    Публикует черновик, создавая новый Shout или обновляя существующий.

    Args:
        draft_id (int): ID черновика для публикации

    Returns:
        dict: Результат публикации с shout или сообщением об ошибке
    """
    author_dict = info.context.get("author") or {}
    author_id = author_dict.get("id")

    if not author_id or not isinstance(author_id, int):
        return {"error": "Author ID is required"}

    try:
        with local_session() as session:
            # Загружаем черновик со всеми связями
            draft = (
                session.query(Draft)
                .options(joinedload(Draft.topics), joinedload(Draft.authors))
                .where(Draft.id == draft_id)
                .first()
            )

            if not draft:
                return {"error": "Draft not found"}

            # Проверка валидности HTML в body
            draft_body = str(draft.body) if draft.body else ""
            is_valid, error = validate_html_content(draft_body)
            if not is_valid:
                return {"error": f"Cannot publish draft: {error}"}

            # Проверяем, есть ли уже публикация для этого черновика
            shout = None
            if hasattr(draft, "publication") and draft.publication:
                shout = draft.publication
                # Обновляем существующую публикацию
                if hasattr(draft, "body"):
                    shout.body = draft.body
                if hasattr(draft, "title"):
                    shout.title = draft.title
                if hasattr(draft, "subtitle"):
                    shout.subtitle = draft.subtitle
                if hasattr(draft, "lead"):
                    shout.lead = draft.lead
                if hasattr(draft, "cover"):
                    shout.cover = draft.cover
                if hasattr(draft, "cover_caption"):
                    shout.cover_caption = draft.cover_caption
                if hasattr(draft, "media"):
                    shout.media = draft.media
                if hasattr(draft, "lang"):
                    shout.lang = draft.lang
                if hasattr(draft, "seo"):
                    shout.seo = draft.seo
                shout.updated_at = int(time.time())
                shout.updated_by = author_id
            else:
                # Создаем новую публикацию
                shout = create_shout_from_draft(session, draft, author_id)
                now = int(time.time())
                shout.created_at = int(now)
                shout.published_at = int(now)
                session.add(shout)
                session.flush()  # Получаем ID нового шаута

            # Очищаем существующие связи
            session.query(ShoutAuthor).where(ShoutAuthor.shout == shout.id).delete()
            session.query(ShoutTopic).where(ShoutTopic.shout == shout.id).delete()

            # Добавляем авторов
            for author in draft.authors or []:
                sa = ShoutAuthor(shout=shout.id, author=author.id)
                session.add(sa)

            # Добавляем темы
            for topic in draft.topics or []:
                st = ShoutTopic(topic=topic.id, shout=shout.id, main=topic.main if hasattr(topic, "main") else False)
                session.add(st)

            session.commit()

            # Инвалидируем кеш
            cache_keys = [
                f"shouts:{shout.id}",
            ]
            await invalidate_shouts_cache(cache_keys)
            await invalidate_shout_related_cache(shout, author_id)

            # Уведомляем о публикации
            await notify_shout(shout.dict(), "published")

            # Обновляем поисковый индекс
            await search_service.perform_index(shout)

            logger.info(f"Successfully published shout #{shout.id} from draft #{draft_id}")
            logger.debug(f"Shout data: {shout.dict()}")

            return {"shout": shout}

    except Exception as e:
        logger.error(f"Failed to publish draft {draft_id}: {e}", exc_info=True)
        return {"error": f"Failed to publish draft: {e!s}"}


@mutation.field("unpublish_draft")
@login_required
async def unpublish_draft(_: None, info: GraphQLResolveInfo, draft_id: int) -> dict[str, Any]:
    """
    Снимает с публикации черновик, обновляя связанный Shout.

    Args:
        draft_id (int): ID черновика, публикацию которого нужно снять

    Returns:
        dict: Результат операции с информацией о черновике или сообщением об ошибке
    """
    author_dict = info.context.get("author") or {}
    author_id = author_dict.get("id")

    if not author_id or not isinstance(author_id, int):
        return {"error": "Author ID is required"}

    try:
        with local_session() as session:
            # Загружаем черновик со связанной публикацией
            draft = (
                session.query(Draft)
                .options(joinedload(Draft.authors), joinedload(Draft.topics))
                .where(Draft.id == draft_id)
                .first()
            )

            if not draft:
                return {"error": "Draft not found"}

            # Проверяем, есть ли публикация
            shout = None
            if hasattr(draft, "publication") and draft.publication:
                shout = draft.publication
            else:
                return {"error": "This draft is not published yet"}

            # Снимаем с публикации
            shout.published_at = None
            shout.updated_at = int(time.time())
            shout.updated_by = author_id

            session.commit()

            # Инвалидируем кэш
            cache_keys = [f"shouts:{shout.id}"]
            await invalidate_shouts_cache(cache_keys)
            await invalidate_shout_related_cache(shout, author_id)

            # Формируем результат
            draft_dict = draft.dict()
            # Добавляем информацию о публикации
            draft_dict["publication"] = {"id": shout.id, "slug": shout.slug, "published_at": None}

            logger.info(f"Successfully unpublished shout #{shout.id} for draft #{draft_id}")

            return {"draft": draft_dict}

    except Exception as e:
        logger.error(f"Failed to unpublish draft {draft_id}: {e}", exc_info=True)
        return {"error": f"Failed to unpublish draft: {e!s}"}
