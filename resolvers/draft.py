import time
from operator import or_

import trafilatura
from sqlalchemy.sql import and_
from sqlalchemy.orm import joinedload

from cache.cache import (
    cache_author,
    cache_by_id,
    cache_topic,
    invalidate_shout_related_cache,
    invalidate_shouts_cache,
)
from orm.author import Author
from orm.draft import Draft
from orm.shout import Shout, ShoutAuthor, ShoutTopic
from orm.topic import Topic
from services.auth import login_required
from services.db import local_session
from services.notify import notify_shout
from services.schema import mutation, query
from services.search import search_service
from utils.logger import root_logger as logger

def create_shout_from_draft(session, draft, author_id):
    # Создаем новую публикацию
    shout = Shout(
        body=draft.body,
        slug=draft.slug,
        cover=draft.cover,
        cover_caption=draft.cover_caption,
        lead=draft.lead,
        title=draft.title,
        subtitle=draft.subtitle,
        layout=draft.layout,
        media=draft.media,
        lang=draft.lang,
        seo=draft.seo,
        created_by=author_id,
        community=draft.community,
        draft=draft.id,
        deleted_at=None,
    )
    return shout


@query.field("load_drafts")
@login_required
async def load_drafts(_, info):
    """
    Загружает все черновики, доступные текущему пользователю.
    
    Предварительно загружает связанные объекты (topics, authors), чтобы избежать
    ошибок с отсоединенными объектами при сериализации.
    
    Returns:
        dict: Список черновиков или сообщение об ошибке
    """
    user_id = info.context.get("user_id")
    author_dict = info.context.get("author", {})
    author_id = author_dict.get("id")

    if not user_id or not author_id:
        return {"error": "User ID and author ID are required"}

    with local_session() as session:
        # Предзагружаем authors и topics, т.к. они lazy='select' в модели
        # created_by, updated_by, deleted_by загрузятся автоматически (lazy='joined')
        drafts = (
            session.query(Draft)
            .options(
                joinedload(Draft.topics),
                joinedload(Draft.authors)
            )
            # Фильтруем по ID автора (создатель или соавтор)
            .filter(or_(Draft.authors.any(Author.id == author_id), Draft.created_by_id == author_id))
            .all()
        )
            
    return {"drafts": drafts}


@mutation.field("create_draft")
@login_required
async def create_draft(_, info, draft_input):
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
    user_id = info.context.get("user_id")
    author_dict = info.context.get("author", {})
    author_id = author_dict.get("id")

    if not user_id or not author_id:
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
            if "id" in draft_input:
                del draft_input["id"]
                
            # Добавляем текущее время создания
            draft_input["created_at"] = int(time.time())
            author = session.query(Author).filter(Author.id == author_id).first()
            draft = Draft(created_by=author, **draft_input)
            session.add(draft)
            session.commit()
            return {"draft": draft}
    except Exception as e:
        logger.error(f"Failed to create draft: {e}", exc_info=True)
        return {"error": f"Failed to create draft: {str(e)}"}

def generate_teaser(body, limit=300):
    body_text = trafilatura.extract(body, include_comments=False, include_tables=False)
    body_teaser = ". ".join(body_text[:limit].split(". ")[:-1])
    return body_teaser


@mutation.field("update_draft")
@login_required
async def update_draft(_, info, draft_id: int, draft_input):
    """Обновляет черновик публикации.

    Args:
        draft_id: ID черновика для обновления
        draft_input: Данные для обновления черновика

    Returns:
        dict: Обновленный черновик или сообщение об ошибке
    """
    user_id = info.context.get("user_id")
    author_dict = info.context.get("author", {})
    author_id = author_dict.get("id")

    if not user_id or not author_id:
        return {"error": "Author ID are required"}

    # Проверяем slug - он должен быть или не пустым, или не передаваться вообще
    if "slug" in draft_input and (draft_input["slug"] is None or draft_input["slug"] == ""):
        # Если slug пустой, либо удаляем его из входных данных, либо генерируем временный уникальный
        # Вариант 1: просто удаляем ключ из входных данных, чтобы оставить старое значение
        del draft_input["slug"]
        # Вариант 2 (если нужно обновить): генерируем временный уникальный slug
        # import uuid
        # draft_input["slug"] = f"draft-{uuid.uuid4().hex[:8]}"

    with local_session() as session:
        draft = session.query(Draft).filter(Draft.id == draft_id).first()
        if not draft:
            return {"error": "Draft not found"}

        # Generate SEO description if not provided and not already set
        if "seo" not in draft_input and not draft.seo:
            body_src = draft_input.get("body") if "body" in draft_input else draft.body
            lead_src = draft_input.get("lead") if "lead" in draft_input else draft.lead

            body_text = None
            if body_src:
                try:
                    # Extract text, excluding comments and tables
                    body_text = trafilatura.extract(body_src, include_comments=False, include_tables=False)
                except Exception as e:
                    logger.warning(f"Trafilatura failed to extract body text for draft {draft_id}: {e}")

            lead_text = None
            if lead_src:
                try:
                    # Extract text from lead
                    lead_text = trafilatura.extract(lead_src, include_comments=False, include_tables=False)
                except Exception as e:
                    logger.warning(f"Trafilatura failed to extract lead text for draft {draft_id}: {e}")

            # Generate body teaser only if body_text was successfully extracted
            body_teaser = generate_teaser(body_text, 300) if body_text else ""

            # Prioritize lead_text for SEO, fallback to body_teaser. Ensure it's a string.
            generated_seo = lead_text if lead_text else body_teaser
            draft_input["seo"] = generated_seo if generated_seo else ""

        # Update the draft object with new data from draft_input
        # Assuming Draft.update is a helper that iterates keys or similar.
        # A more standard SQLAlchemy approach would be:
        # for key, value in draft_input.items():
        #     if hasattr(draft, key):
        #         setattr(draft, key, value)
        # But we stick to the existing pattern for now.
        Draft.update(draft, draft_input)

        # Set updated timestamp and author
        current_time = int(time.time())
        draft.updated_at = current_time
        draft.updated_by = author_id # Assuming author_id is correctly fetched context

        session.commit()
        # Invalidate cache related to this draft if necessary (consider adding)
        # await invalidate_draft_cache(draft_id)
        return {"draft": draft}


@mutation.field("delete_draft")
@login_required
async def delete_draft(_, info, draft_id: int):
    author_dict = info.context.get("author", {})
    author_id = author_dict.get("id")

    with local_session() as session:
        draft = session.query(Draft).filter(Draft.id == draft_id).first()
        if not draft:
            return {"error": "Draft not found"}
        if author_id != draft.created_by and draft.authors.filter(Author.id == author_id).count() == 0:
            return {"error": "You are not allowed to delete this draft"}
        session.delete(draft)
        session.commit()
        return {"draft": draft}


@mutation.field("publish_draft")
@login_required
async def publish_draft(_, info, draft_id: int):
    """Публикует черновик в виде публикации (shout).
    
    Загружает связанные объекты (topics, authors) заранее, чтобы избежать ошибок
    с отсоединенными объектами при сериализации.
    
    Args:
        draft_id: ID черновика для публикации
        
    Returns:
        dict: Опубликованная публикация и черновик или сообщение об ошибке
    """
    user_id = info.context.get("user_id")
    author_dict = info.context.get("author", {})
    author_id = author_dict.get("id")
    if not user_id or not author_id:
        return {"error": "User ID and author ID are required"}
    
    now = int(time.time())
    
    try:
        with local_session() as session:
            shout_id = session.query(Draft.shout).filter(Draft.id == draft_id).first()
            shout = session.query(Shout).filter(Shout.id == shout_id).first()
            if not shout:
                return {"error": "Shout not found"}
            was_published = shout.published_at is not None
            draft = session.query(Draft).where(Draft.id == shout.draft).first()
            if not draft:
                return {"error": "Draft not found"}
            # Находим черновик если не передан

            if not shout:
                shout = create_shout_from_draft(session, draft, author_id)
            else:
                # Обновляем существующую публикацию
                shout.draft = draft.id
                shout.created_by = author_id
                shout.title = draft.title
                shout.subtitle = draft.subtitle
                shout.body = draft.body
                shout.cover = draft.cover
                shout.cover_caption = draft.cover_caption
                shout.lead = draft.lead
                shout.layout = draft.layout
                shout.media = draft.media
                shout.lang = draft.lang
                shout.seo = draft.seo

                draft.updated_at = now
                shout.updated_at = now

                # Устанавливаем published_at только если была ранее снята с публикации
                if not was_published:
                    shout.published_at = now

            # Обрабатываем связи с авторами
            if (
                not session.query(ShoutAuthor)
                .filter(and_(ShoutAuthor.shout == shout.id, ShoutAuthor.author == author_id))
                .first()
            ):
                sa = ShoutAuthor(shout=shout.id, author=author_id)
                session.add(sa)

            # Обрабатываем темы
            if draft.topics:
                for topic in draft.topics:
                    st = ShoutTopic(
                        topic=topic.id, shout=shout.id, main=topic.main if hasattr(topic, "main") else False
                    )
                    session.add(st)

            session.add(shout)
            session.add(draft)
            session.flush()

            # Инвалидируем кэш только если это новая публикация или была снята с публикации
            if not was_published:
                cache_keys = ["feed", f"author_{author_id}", "random_top", "unrated"]

                # Добавляем ключи для тем
                for topic in shout.topics:
                    cache_keys.append(f"topic_{topic.id}")
                    cache_keys.append(f"topic_shouts_{topic.id}")
                    await cache_by_id(Topic, topic.id, cache_topic)

                # Инвалидируем кэш
                await invalidate_shouts_cache(cache_keys)
                await invalidate_shout_related_cache(shout, author_id)

                # Обновляем кэш авторов
                for author in shout.authors:
                    await cache_by_id(Author, author.id, cache_author)

                # Отправляем уведомление о публикации
                await notify_shout(shout.dict(), "published")

                # Обновляем поисковый индекс
                search_service.index(shout)
            else:
                # Для уже опубликованных материалов просто отправляем уведомление об обновлении
                await notify_shout(shout.dict(), "update")

            session.commit()
            return {"shout": shout}

    except Exception as e:
        logger.error(f"Failed to publish shout: {e}", exc_info=True)
        if "session" in locals():
            session.rollback()
        return {"error": f"Failed to publish shout: {str(e)}"}
