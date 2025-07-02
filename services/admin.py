"""
Сервис админ-панели с бизнес-логикой для управления пользователями, публикациями и приглашениями.
"""

from math import ceil
from typing import Any

from sqlalchemy import String, cast, null, or_
from sqlalchemy.orm import joinedload
from sqlalchemy.sql import func, select

from auth.orm import Author
from orm.community import Community, CommunityAuthor
from orm.invite import Invite, InviteStatus
from orm.shout import Shout
from services.db import local_session
from services.env import EnvManager, EnvVariable
from utils.logger import root_logger as logger


class AdminService:
    """Сервис для админ-панели с бизнес-логикой"""

    @staticmethod
    def normalize_pagination(limit: int = 20, offset: int = 0) -> tuple[int, int]:
        """Нормализует параметры пагинации"""
        return max(1, min(100, limit or 20)), max(0, offset or 0)

    @staticmethod
    def calculate_pagination_info(total_count: int, limit: int, offset: int) -> dict[str, int]:
        """Вычисляет информацию о пагинации"""
        per_page = limit
        if total_count is None or per_page in (None, 0):
            total_pages = 1
        else:
            total_pages = ceil(total_count / per_page)
        current_page = (offset // per_page) + 1 if per_page > 0 else 1

        return {
            "total": total_count,
            "page": current_page,
            "perPage": per_page,
            "totalPages": total_pages,
        }

    @staticmethod
    def get_author_info(author_id: int, session) -> dict[str, Any]:
        """Получает информацию об авторе"""
        if not author_id or author_id == 0:
            return {
                "id": 0,
                "email": "system@discours.io",
                "name": "System",
                "slug": "system",
            }

        author = session.query(Author).filter(Author.id == author_id).first()
        if author:
            return {
                "id": author.id,
                "email": author.email or f"user{author.id}@discours.io",
                "name": author.name or f"User {author.id}",
                "slug": author.slug or f"user-{author.id}",
            }
        return {
            "id": author_id,
            "email": f"deleted{author_id}@discours.io",
            "name": f"Deleted User {author_id}",
            "slug": f"deleted-user-{author_id}",
        }

    @staticmethod
    def get_user_roles(user: Author, community_id: int = 1) -> list[str]:
        """Получает роли пользователя в сообществе"""
        from settings import ADMIN_EMAILS as ADMIN_EMAILS_LIST

        admin_emails = ADMIN_EMAILS_LIST.split(",") if ADMIN_EMAILS_LIST else []
        user_roles = []

        with local_session() as session:
            community_author = (
                session.query(CommunityAuthor)
                .filter(CommunityAuthor.author_id == user.id, CommunityAuthor.community_id == community_id)
                .first()
            )

            if community_author:
                user_roles = community_author.role_list

        # Добавляем синтетическую роль для системных админов
        if user.email and user.email.lower() in [email.lower() for email in admin_emails]:
            if "Системный администратор" not in user_roles:
                user_roles.insert(0, "Системный администратор")

        return user_roles

    # === ПОЛЬЗОВАТЕЛИ ===

    def get_users(self, limit: int = 20, offset: int = 0, search: str = "") -> dict[str, Any]:
        """Получает список пользователей"""
        limit, offset = self.normalize_pagination(limit, offset)

        with local_session() as session:
            query = session.query(Author)

            if search and search.strip():
                search_term = f"%{search.strip().lower()}%"
                query = query.filter(
                    or_(
                        Author.email.ilike(search_term),
                        Author.name.ilike(search_term),
                        cast(Author.id, String).ilike(search_term),
                    )
                )

            total_count = query.count()
            authors = query.order_by(Author.id).offset(offset).limit(limit).all()
            pagination_info = self.calculate_pagination_info(total_count, limit, offset)

            return {
                "authors": [
                    {
                        "id": user.id,
                        "email": user.email,
                        "name": user.name,
                        "slug": user.slug,
                        "roles": self.get_user_roles(user, 1),
                        "created_at": user.created_at,
                        "last_seen": user.last_seen,
                    }
                    for user in authors
                ],
                **pagination_info,
            }

    def update_user(self, user_data: dict[str, Any]) -> dict[str, Any]:
        """Обновляет данные пользователя"""
        user_id = user_data.get("id")
        if not user_id:
            return {"success": False, "error": "ID пользователя не указан"}

        try:
            user_id_int = int(user_id)
        except (TypeError, ValueError):
            return {"success": False, "error": "Некорректный ID пользователя"}

        roles = user_data.get("roles", [])
        email = user_data.get("email")
        name = user_data.get("name")
        slug = user_data.get("slug")

        with local_session() as session:
            author = session.query(Author).filter(Author.id == user_id).first()
            if not author:
                return {"success": False, "error": f"Пользователь с ID {user_id} не найден"}

            # Обновляем основные поля
            if email is not None and email != author.email:
                existing = session.query(Author).filter(Author.email == email, Author.id != user_id).first()
                if existing:
                    return {"success": False, "error": f"Email {email} уже используется"}
                author.email = email

            if name is not None and name != author.name:
                author.name = name

            if slug is not None and slug != author.slug:
                existing = session.query(Author).filter(Author.slug == slug, Author.id != user_id).first()
                if existing:
                    return {"success": False, "error": f"Slug {slug} уже используется"}
                author.slug = slug

            # Обновляем роли
            if roles is not None:
                community_author = (
                    session.query(CommunityAuthor)
                    .filter(CommunityAuthor.author_id == user_id_int, CommunityAuthor.community_id == 1)
                    .first()
                )

                if not community_author:
                    community_author = CommunityAuthor(author_id=user_id_int, community_id=1, roles="")
                    session.add(community_author)

                # Валидация ролей
                all_roles = ["reader", "author", "artist", "expert", "editor", "admin"]
                valid_roles = [role for role in roles if role in all_roles]
                community_author.set_roles(valid_roles)
            session.commit()
            logger.info(f"Пользователь {author.email or author.id} обновлен")
            return {"success": True}

    # === ПУБЛИКАЦИИ ===

    def get_shouts(
        self,
        limit: int = 20,
        offset: int = 0,
        search: str = "",
        status: str = "all",
        community: int = None,
    ) -> dict[str, Any]:
        """Получает список публикаций"""
        limit = max(1, min(100, limit or 10))
        offset = max(0, offset or 0)

        with local_session() as session:
            q = select(Shout).options(joinedload(Shout.authors), joinedload(Shout.topics))

            # Фильтр статуса
            if status == "published":
                q = q.filter(Shout.published_at.isnot(None), Shout.deleted_at.is_(None))
            elif status == "draft":
                q = q.filter(Shout.published_at.is_(None), Shout.deleted_at.is_(None))
            elif status == "deleted":
                q = q.filter(Shout.deleted_at.isnot(None))

            # Фильтр по сообществу
            if community is not None:
                q = q.filter(Shout.community == community)

            # Поиск
            if search and search.strip():
                search_term = f"%{search.strip().lower()}%"
                q = q.filter(
                    or_(
                        Shout.title.ilike(search_term),
                        Shout.slug.ilike(search_term),
                        cast(Shout.id, String).ilike(search_term),
                        Shout.body.ilike(search_term),
                    )
                )

            total_count = session.execute(select(func.count()).select_from(q.subquery())).scalar()
            q = q.order_by(Shout.created_at.desc()).limit(limit).offset(offset)
            shouts_result = session.execute(q).unique().scalars().all()

            shouts_data = []
            for shout in shouts_result:
                shout_dict = self._serialize_shout(shout, session)
                if shout_dict is not None:  # Фильтруем объекты с отсутствующими обязательными полями
                    shouts_data.append(shout_dict)

            per_page = limit or 20
            total_pages = ceil((total_count or 0) / per_page) if per_page > 0 else 1
            current_page = (offset // per_page) + 1 if per_page > 0 else 1

            return {
                "shouts": shouts_data,
                "total": total_count,
                "page": current_page,
                "perPage": per_page,
                "totalPages": total_pages,
            }

    def _serialize_shout(self, shout, session) -> dict[str, Any] | None:
        """Сериализует публикацию в словарь"""
        # Проверяем обязательные поля перед сериализацией
        if not hasattr(shout, "id") or not shout.id:
            logger.warning(f"Shout без ID найден, пропускаем: {shout}")
            return None

        # Обрабатываем media
        media_data = []
        if hasattr(shout, "media") and shout.media:
            if isinstance(shout.media, str):
                try:
                    import orjson

                    media_data = orjson.loads(shout.media)
                except Exception:
                    media_data = []
            elif isinstance(shout.media, list):
                media_data = shout.media

        # Получаем информацию о создателе (обязательное поле)
        created_by_info = self.get_author_info(getattr(shout, "created_by", None) or 0, session)

        # Получаем информацию о сообществе (обязательное поле)
        community_info = self._get_community_info(getattr(shout, "community", None) or 0, session)

        return {
            "id": shout.id,  # Обязательное поле
            "title": getattr(shout, "title", "") or "",  # Обязательное поле
            "slug": getattr(shout, "slug", "") or f"shout-{shout.id}",  # Обязательное поле
            "body": getattr(shout, "body", "") or "",  # Обязательное поле
            "lead": getattr(shout, "lead", None),
            "subtitle": getattr(shout, "subtitle", None),
            "layout": getattr(shout, "layout", "article") or "article",  # Обязательное поле
            "lang": getattr(shout, "lang", "ru") or "ru",  # Обязательное поле
            "cover": getattr(shout, "cover", None),
            "cover_caption": getattr(shout, "cover_caption", None),
            "media": media_data,
            "seo": getattr(shout, "seo", None),
            "created_at": getattr(shout, "created_at", 0) or 0,  # Обязательное поле
            "updated_at": getattr(shout, "updated_at", None),
            "published_at": getattr(shout, "published_at", None),
            "featured_at": getattr(shout, "featured_at", None),
            "deleted_at": getattr(shout, "deleted_at", None),
            "created_by": created_by_info,  # Обязательное поле
            "updated_by": self.get_author_info(getattr(shout, "updated_by", None) or 0, session),
            "deleted_by": self.get_author_info(getattr(shout, "deleted_by", None) or 0, session),
            "community": community_info,  # Обязательное поле
            "authors": [
                {
                    "id": getattr(author, "id", None),
                    "email": getattr(author, "email", None),
                    "name": getattr(author, "name", None),
                    "slug": getattr(author, "slug", None) or f"user-{getattr(author, 'id', 'unknown')}",
                }
                for author in getattr(shout, "authors", [])
            ],
            "topics": [
                {
                    "id": getattr(topic, "id", None),
                    "title": getattr(topic, "title", None),
                    "slug": getattr(topic, "slug", None),
                }
                for topic in getattr(shout, "topics", [])
            ],
            "version_of": getattr(shout, "version_of", None),
            "draft": getattr(shout, "draft", None),
            "stat": None,
        }

    def _get_community_info(self, community_id: int, session) -> dict[str, Any]:
        """Получает информацию о сообществе"""
        if not community_id or community_id == 0:
            return {
                "id": 1,  # Default community ID
                "name": "Дискурс",
                "slug": "discours",
            }

        community = session.query(Community).filter(Community.id == community_id).first()
        if community:
            return {
                "id": community.id,
                "name": community.name or f"Community {community.id}",
                "slug": community.slug or f"community-{community.id}",
            }
        return {
            "id": community_id,
            "name": f"Unknown Community {community_id}",
            "slug": f"unknown-community-{community_id}",
        }

    def restore_shout(self, shout_id: int) -> dict[str, Any]:
        """Восстанавливает удаленную публикацию"""
        with local_session() as session:
            shout = session.query(Shout).filter(Shout.id == shout_id).first()

            if not shout:
                return {"success": False, "error": f"Публикация с ID {shout_id} не найдена"}

            if not shout.deleted_at:
                return {"success": False, "error": "Публикация не была удалена"}

            shout.deleted_at = null()
            shout.deleted_by = null()
            session.commit()

            logger.info(f"Публикация {shout.title or shout.id} восстановлена")
            return {"success": True}

    # === ПРИГЛАШЕНИЯ ===

    def get_invites(self, limit: int = 20, offset: int = 0, search: str = "", status: str = "all") -> dict[str, Any]:
        """Получает список приглашений"""
        limit, offset = self.normalize_pagination(limit, offset)

        with local_session() as session:
            query = session.query(Invite).options(
                joinedload(Invite.inviter),
                joinedload(Invite.author),
                joinedload(Invite.shout),
            )

            # Фильтр по статусу
            if status and status != "all":
                status_enum = InviteStatus[status.upper()]
                query = query.filter(Invite.status == status_enum.value)

            # Поиск
            if search and search.strip():
                search_term = f"%{search.strip().lower()}%"
                query = query.filter(
                    or_(
                        Invite.inviter.has(Author.email.ilike(search_term)),
                        Invite.inviter.has(Author.name.ilike(search_term)),
                        Invite.author.has(Author.email.ilike(search_term)),
                        Invite.author.has(Author.name.ilike(search_term)),
                        Invite.shout.has(Shout.title.ilike(search_term)),
                        cast(Invite.inviter_id, String).ilike(search_term),
                        cast(Invite.author_id, String).ilike(search_term),
                        cast(Invite.shout_id, String).ilike(search_term),
                    )
                )

            total_count = query.count()
            invites = (
                query.order_by(Invite.inviter_id, Invite.author_id, Invite.shout_id).offset(offset).limit(limit).all()
            )
            pagination_info = self.calculate_pagination_info(total_count, limit, offset)

            result_invites = []
            for invite in invites:
                created_by_info = self.get_author_info(
                    (invite.shout.created_by if invite.shout else None) or 0, session
                )

                result_invites.append(
                    {
                        "inviter_id": invite.inviter_id,
                        "author_id": invite.author_id,
                        "shout_id": invite.shout_id,
                        "status": invite.status,
                        "inviter": {
                            "id": invite.inviter.id,
                            "name": invite.inviter.name or "Без имени",
                            "email": invite.inviter.email,
                            "slug": invite.inviter.slug or f"user-{invite.inviter.id}",
                        },
                        "author": {
                            "id": invite.author.id,
                            "name": invite.author.name or "Без имени",
                            "email": invite.author.email,
                            "slug": invite.author.slug or f"user-{invite.author.id}",
                        },
                        "shout": {
                            "id": invite.shout.id,
                            "title": invite.shout.title,
                            "slug": invite.shout.slug,
                            "created_by": created_by_info,
                        },
                        "created_at": None,
                    }
                )

            return {
                "invites": result_invites,
                **pagination_info,
            }

    def update_invite(self, invite_data: dict[str, Any]) -> dict[str, Any]:
        """Обновляет приглашение"""
        inviter_id = invite_data["inviter_id"]
        author_id = invite_data["author_id"]
        shout_id = invite_data["shout_id"]
        new_status = invite_data["status"]

        with local_session() as session:
            invite = (
                session.query(Invite)
                .filter(
                    Invite.inviter_id == inviter_id,
                    Invite.author_id == author_id,
                    Invite.shout_id == shout_id,
                )
                .first()
            )

            if not invite:
                return {"success": False, "error": "Приглашение не найдено"}

            old_status = invite.status
            invite.status = new_status
            session.commit()

            logger.info(f"Статус приглашения обновлен: {old_status} → {new_status}")
            return {"success": True, "error": None}

    def delete_invite(self, inviter_id: int, author_id: int, shout_id: int) -> dict[str, Any]:
        """Удаляет приглашение"""
        with local_session() as session:
            invite = (
                session.query(Invite)
                .filter(
                    Invite.inviter_id == inviter_id,
                    Invite.author_id == author_id,
                    Invite.shout_id == shout_id,
                )
                .first()
            )

            if not invite:
                return {"success": False, "error": "Приглашение не найдено"}

            session.delete(invite)
            session.commit()

            logger.info(f"Приглашение {inviter_id}-{author_id}-{shout_id} удалено")
            return {"success": True, "error": None}

    # === ПЕРЕМЕННЫЕ ОКРУЖЕНИЯ ===

    async def get_env_variables(self) -> list[dict[str, Any]]:
        """Получает переменные окружения"""
        env_manager = EnvManager()
        sections = await env_manager.get_all_variables()

        return [
            {
                "name": section.name,
                "description": section.description,
                "variables": [
                    {
                        "key": var.key,
                        "value": var.value,
                        "description": var.description,
                        "type": var.type,
                        "isSecret": var.is_secret,
                    }
                    for var in section.variables
                ],
            }
            for section in sections
        ]

    async def update_env_variable(self, key: str, value: str) -> dict[str, Any]:
        """Обновляет переменную окружения"""
        try:
            env_manager = EnvManager()
            result = env_manager.update_variables([EnvVariable(key=key, value=value)])

            if result:
                logger.info(f"Переменная '{key}' обновлена")
                return {"success": True, "error": None}
            return {"success": False, "error": f"Не удалось обновить переменную '{key}'"}
        except Exception as e:
            logger.error(f"Ошибка обновления переменной: {e}")
            return {"success": False, "error": str(e)}

    async def update_env_variables(self, variables: list[dict[str, Any]]) -> dict[str, Any]:
        """Массовое обновление переменных окружения"""
        try:
            env_manager = EnvManager()
            env_variables = [
                EnvVariable(key=var.get("key", ""), value=var.get("value", ""), type=var.get("type", "string"))
                for var in variables
            ]

            result = env_manager.update_variables(env_variables)

            if result:
                logger.info(f"Обновлено {len(variables)} переменных")
                return {"success": True, "error": None}
            return {"success": False, "error": "Не удалось обновить переменные"}
        except Exception as e:
            logger.error(f"Ошибка массового обновления: {e}")
            return {"success": False, "error": str(e)}

    # === РОЛИ ===

    def get_roles(self, community: int = None) -> list[dict[str, Any]]:
        """Получает список ролей"""
        from orm.community import role_descriptions, role_names

        all_roles = ["reader", "author", "artist", "expert", "editor", "admin"]

        if community is not None:
            with local_session() as session:
                community_obj = session.query(Community).filter(Community.id == community).first()
                available_roles = community_obj.get_available_roles() if community_obj else all_roles
        else:
            available_roles = all_roles

        return [
            {
                "id": role_id,
                "name": role_names.get(role_id, role_id.title()),
                "description": role_descriptions.get(role_id, f"Роль {role_id}"),
            }
            for role_id in available_roles
        ]


# Синглтон сервиса
admin_service = AdminService()
