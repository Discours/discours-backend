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
from orm.draft import Draft, DraftAuthor, DraftTopic
from orm.shout import Shout, ShoutAuthor, ShoutTopic
from orm.topic import Topic
from services.auth import login_required
from services.db import local_session
from services.notify import notify_shout
from services.schema import mutation, query
from services.search import search_service
from utils.html_wrapper import wrap_html_fragment
from utils.logger import root_logger as logger

def create_shout_from_draft(session, draft, author_id):
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

    try:
        with local_session() as session:
            # Предзагружаем authors и topics
            drafts = (
                session.query(Draft)
                .options(
                    joinedload(Draft.topics),
                    joinedload(Draft.authors)
                )
                .filter(Draft.authors.any(Author.id == author_id))
                .all()
            )
            
            # Преобразуем объекты в словари, пока они в контексте сессии
            drafts_data = []
            for draft in drafts:
                draft_dict = draft.dict()
                draft_dict["topics"] = [topic.dict() for topic in draft.topics]
                draft_dict["authors"] = [author.dict() for author in draft.authors]
                drafts_data.append(draft_dict)
                
            return {"drafts": drafts_data}
    except Exception as e:
        logger.error(f"Failed to load drafts: {e}", exc_info=True)
        return {"error": f"Failed to load drafts: {str(e)}"}


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
                
            # Добавляем текущее время создания и ID автора
            draft_input["created_at"] = int(time.time())
            draft_input["created_by"] = author_id
            draft = Draft(**draft_input)
            session.add(draft)
            session.flush()
            
            # Добавляем создателя как автора
            da = DraftAuthor(shout=draft.id, author=author_id)
            session.add(da)
            
            session.commit()
            return {"draft": draft}
    except Exception as e:
        logger.error(f"Failed to create draft: {e}", exc_info=True)
        return {"error": f"Failed to create draft: {str(e)}"}

def generate_teaser(body, limit=300):
    body_html = wrap_html_fragment(body)
    body_text = trafilatura.extract(body_html, include_comments=False, include_tables=False)
    body_teaser = ". ".join(body_text[:limit].split(". ")[:-1])
    return body_teaser


@mutation.field("update_draft")
@login_required
async def update_draft(_, info, draft_id: int, draft_input):
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
    user_id = info.context.get("user_id")
    author_dict = info.context.get("author", {})
    author_id = author_dict.get("id")

    if not user_id or not author_id:
        return {"error": "Author ID are required"}

    try:
        with local_session() as session:
            draft = session.query(Draft).filter(Draft.id == draft_id).first()
            if not draft:
                return {"error": "Draft not found"}

            # Фильтруем входные данные, оставляя только разрешенные поля
            allowed_fields = {
                "layout", "author_ids", "topic_ids", "main_topic_id", 
                "media", "lead", "subtitle", "lang", "seo", "body", 
                "title", "slug", "cover", "cover_caption"
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
                    session.query(DraftAuthor).filter(DraftAuthor.shout == draft_id).delete()
                    # Добавляем новые связи
                    for aid in author_ids:
                        da = DraftAuthor(shout=draft_id, author=aid)
                        session.add(da)

            # Обновляем связи с темами если переданы
            if "topic_ids" in filtered_input:
                topic_ids = filtered_input.pop("topic_ids")
                main_topic_id = filtered_input.pop("main_topic_id", None)
                if topic_ids:
                    # Очищаем текущие связи
                    session.query(DraftTopic).filter(DraftTopic.shout == draft_id).delete()
                    # Добавляем новые связи
                    for tid in topic_ids:
                        dt = DraftTopic(
                            shout=draft_id, 
                            topic=tid,
                            main=(tid == main_topic_id) if main_topic_id else False
                        )
                        session.add(dt)

            # Генерируем SEO если не предоставлено
            if "seo" not in filtered_input and not draft.seo:
                body_src = filtered_input.get("body", draft.body)
                lead_src = filtered_input.get("lead", draft.lead)
                body_html = wrap_html_fragment(body_src)
                lead_html = wrap_html_fragment(lead_src)
                
                try:
                    body_text = trafilatura.extract(body_html, include_comments=False, include_tables=False) if body_src else None
                    lead_text = trafilatura.extract(lead_html, include_comments=False, include_tables=False) if lead_src else None
                    
                    body_teaser = generate_teaser(body_text, 300) if body_text else ""
                    filtered_input["seo"] = lead_text if lead_text else body_teaser
                except Exception as e:
                    logger.warning(f"Failed to generate SEO for draft {draft_id}: {e}")

            # Обновляем основные поля черновика
            for key, value in filtered_input.items():
                setattr(draft, key, value)

            # Обновляем метаданные
            draft.updated_at = int(time.time())
            draft.updated_by = author_id

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
        return {"error": f"Failed to update draft: {str(e)}"}


@mutation.field("delete_draft")
@login_required
async def delete_draft(_, info, draft_id: int):
    author_dict = info.context.get("author", {})
    author_id = author_dict.get("id")

    with local_session() as session:
        draft = session.query(Draft).filter(Draft.id == draft_id).first()
        if not draft:
            return {"error": "Draft not found"}
        if author_id != draft.created_by_id and draft.authors.filter(Author.id == author_id).count() == 0:
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
        html_content = wrap_html_fragment(html_content)
        extracted = trafilatura.extract(html_content)
        if not extracted:
            return False, "Invalid HTML structure or empty content"
        return True, ""
    except Exception as e:
        logger.error(f"HTML validation error: {e}", exc_info=True)
        return False, f"Invalid HTML content: {str(e)}"


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
            # Сначала находим черновик
            draft = session.query(Draft).filter(Draft.id == draft_id).first()
            if not draft:
                return {"error": "Draft not found"}

            # Проверка валидности HTML в body
            is_valid, error = validate_html_content(draft.body)
            if not is_valid:
                return {"error": f"Cannot publish draft: {error}"}

            # Ищем существующий shout для этого черновика
            shout = session.query(Shout).filter(Shout.draft == draft_id).first()
            was_published = shout.published_at if shout else None

            if not shout:
                # Создаем новый shout если не существует
                shout = create_shout_from_draft(session, draft, author_id)
                shout.published_at = now
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
                shout.updated_at = now
                
                # Устанавливаем published_at только если была ранее снята с публикации
                if not was_published:
                    shout.published_at = now

            # Сохраняем shout перед созданием связей
            session.add(shout)
            session.flush()

            # Очищаем существующие связи
            session.query(ShoutAuthor).filter(ShoutAuthor.shout == shout.id).delete()
            session.query(ShoutTopic).filter(ShoutTopic.shout == shout.id).delete()

            # Добавляем автора
            sa = ShoutAuthor(shout=shout.id, author=author_id)
            session.add(sa)

            # Добавляем темы если есть
            if draft.topics:
                for topic in draft.topics:
                    st = ShoutTopic(
                        topic=topic.id, 
                        shout=shout.id, 
                        main=topic.main if hasattr(topic, "main") else False
                    )
                    session.add(st)

            # Обновляем черновик
            draft.updated_at = now
            session.add(draft)

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
            shout_dict = shout.dict()
            # Добавляем объект автора в updated_by
            shout_dict["updated_by"] = author_dict
            return {"shout": shout_dict}

    except Exception as e:
        logger.error(f"Failed to publish shout: {e}", exc_info=True)
        if "session" in locals():
            session.rollback()
        return {"error": f"Failed to publish shout: {str(e)}"}
