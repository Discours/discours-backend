import os
import re
from dataclasses import dataclass
from typing import Dict, List, Literal, Optional

from services.redis import redis
from utils.logger import root_logger as logger


@dataclass
class EnvVariable:
    """Представление переменной окружения"""

    key: str
    value: str = ""
    description: str = ""
    type: Literal["string", "integer", "boolean", "json"] = "string"  # string, integer, boolean, json
    is_secret: bool = False


@dataclass
class EnvSection:
    """Группа переменных окружения"""

    name: str
    description: str
    variables: List[EnvVariable]


class EnvManager:
    """
    Менеджер переменных окружения с поддержкой Redis кеширования
    """

    # Определение секций с их описаниями
    SECTIONS = {
        "database": "Настройки базы данных",
        "auth": "Настройки аутентификации",
        "redis": "Настройки Redis",
        "search": "Настройки поиска",
        "integrations": "Внешние интеграции",
        "security": "Настройки безопасности",
        "logging": "Настройки логирования",
        "features": "Флаги функций",
        "other": "Прочие настройки",
    }

    # Маппинг переменных на секции
    VARIABLE_SECTIONS = {
        # Database
        "DB_URL": "database",
        "DATABASE_URL": "database",
        "POSTGRES_USER": "database",
        "POSTGRES_PASSWORD": "database",
        "POSTGRES_DB": "database",
        "POSTGRES_HOST": "database",
        "POSTGRES_PORT": "database",
        # Auth
        "JWT_SECRET": "auth",
        "JWT_ALGORITHM": "auth",
        "JWT_EXPIRATION": "auth",
        "SECRET_KEY": "auth",
        "AUTH_SECRET": "auth",
        "OAUTH_GOOGLE_CLIENT_ID": "auth",
        "OAUTH_GOOGLE_CLIENT_SECRET": "auth",
        "OAUTH_GITHUB_CLIENT_ID": "auth",
        "OAUTH_GITHUB_CLIENT_SECRET": "auth",
        # Redis
        "REDIS_URL": "redis",
        "REDIS_HOST": "redis",
        "REDIS_PORT": "redis",
        "REDIS_PASSWORD": "redis",
        "REDIS_DB": "redis",
        # Search
        "SEARCH_API_KEY": "search",
        "ELASTICSEARCH_URL": "search",
        "SEARCH_INDEX": "search",
        # Integrations
        "GOOGLE_ANALYTICS_ID": "integrations",
        "SENTRY_DSN": "integrations",
        "SMTP_HOST": "integrations",
        "SMTP_PORT": "integrations",
        "SMTP_USER": "integrations",
        "SMTP_PASSWORD": "integrations",
        "EMAIL_FROM": "integrations",
        # Security
        "CORS_ORIGINS": "security",
        "ALLOWED_HOSTS": "security",
        "SECURE_SSL_REDIRECT": "security",
        "SESSION_COOKIE_SECURE": "security",
        "CSRF_COOKIE_SECURE": "security",
        # Logging
        "LOG_LEVEL": "logging",
        "LOG_FORMAT": "logging",
        "LOG_FILE": "logging",
        "DEBUG": "logging",
        # Features
        "FEATURE_REGISTRATION": "features",
        "FEATURE_COMMENTS": "features",
        "FEATURE_ANALYTICS": "features",
        "FEATURE_SEARCH": "features",
    }

    # Секретные переменные (не показываем их значения в UI)
    SECRET_VARIABLES = {
        "JWT_SECRET",
        "SECRET_KEY",
        "AUTH_SECRET",
        "OAUTH_GOOGLE_CLIENT_SECRET",
        "OAUTH_GITHUB_CLIENT_SECRET",
        "POSTGRES_PASSWORD",
        "REDIS_PASSWORD",
        "SEARCH_API_KEY",
        "SENTRY_DSN",
        "SMTP_PASSWORD",
    }

    def __init__(self) -> None:
        self.redis_prefix = "env_vars:"

    def _get_variable_type(self, key: str, value: str) -> Literal["string", "integer", "boolean", "json"]:
        """Определяет тип переменной на основе ключа и значения"""

        # Boolean переменные
        if value.lower() in ("true", "false", "1", "0", "yes", "no"):
            return "boolean"

        # Integer переменные
        if key.endswith(("_PORT", "_TIMEOUT", "_LIMIT", "_SIZE")) or value.isdigit():
            return "integer"

        # JSON переменные
        if value.startswith(("{", "[")) and value.endswith(("}", "]")):
            return "json"

        return "string"

    def _get_variable_description(self, key: str) -> str:
        """Генерирует описание для переменной на основе её ключа"""

        descriptions = {
            "DB_URL": "URL подключения к базе данных",
            "REDIS_URL": "URL подключения к Redis",
            "JWT_SECRET": "Секретный ключ для подписи JWT токенов",
            "CORS_ORIGINS": "Разрешенные CORS домены",
            "DEBUG": "Режим отладки (true/false)",
            "LOG_LEVEL": "Уровень логирования (DEBUG, INFO, WARNING, ERROR)",
            "SENTRY_DSN": "DSN для интеграции с Sentry",
            "GOOGLE_ANALYTICS_ID": "ID для Google Analytics",
            "OAUTH_GOOGLE_CLIENT_ID": "Client ID для OAuth Google",
            "OAUTH_GOOGLE_CLIENT_SECRET": "Client Secret для OAuth Google",
            "OAUTH_GITHUB_CLIENT_ID": "Client ID для OAuth GitHub",
            "OAUTH_GITHUB_CLIENT_SECRET": "Client Secret для OAuth GitHub",
            "SMTP_HOST": "SMTP сервер для отправки email",
            "SMTP_PORT": "Порт SMTP сервера",
            "SMTP_USER": "Пользователь SMTP",
            "SMTP_PASSWORD": "Пароль SMTP",
            "EMAIL_FROM": "Email отправителя по умолчанию",
        }

        return descriptions.get(key, f"Переменная окружения {key}")

    async def get_variables_from_redis(self) -> Dict[str, str]:
        """Получает переменные из Redis"""

        try:
            # Get all keys matching our prefix
            pattern = f"{self.redis_prefix}*"
            keys = await redis.execute("KEYS", pattern)

            if not keys:
                return {}

            redis_vars: Dict[str, str] = {}
            for key in keys:
                var_key = key.replace(self.redis_prefix, "")
                value = await redis.get(key)
                if value:
                    if isinstance(value, bytes):
                        redis_vars[var_key] = value.decode("utf-8")
                    else:
                        redis_vars[var_key] = str(value)

            return redis_vars

        except Exception as e:
            logger.error(f"Ошибка при получении переменных из Redis: {e}")
            return {}

    async def set_variables_to_redis(self, variables: Dict[str, str]) -> bool:
        """Сохраняет переменные в Redis"""

        try:
            for key, value in variables.items():
                redis_key = f"{self.redis_prefix}{key}"
                await redis.set(redis_key, value)

            logger.info(f"Сохранено {len(variables)} переменных в Redis")
            return True

        except Exception as e:
            logger.error(f"Ошибка при сохранении переменных в Redis: {e}")
            return False

    def get_variables_from_env(self) -> Dict[str, str]:
        """Получает переменные из системного окружения"""

        env_vars = {}

        # Получаем все переменные известные системе
        for key in self.VARIABLE_SECTIONS.keys():
            value = os.getenv(key)
            if value is not None:
                env_vars[key] = value

        # Также ищем переменные по паттернам
        for env_key, env_value in os.environ.items():
            # Переменные проекта обычно начинаются с определенных префиксов
            if any(env_key.startswith(prefix) for prefix in ["APP_", "SITE_", "FEATURE_", "OAUTH_"]):
                env_vars[env_key] = env_value

        return env_vars

    async def get_all_variables(self) -> List[EnvSection]:
        """Получает все переменные окружения, сгруппированные по секциям"""

        # Получаем переменные из разных источников
        env_vars = self.get_variables_from_env()
        redis_vars = await self.get_variables_from_redis()

        # Объединяем переменные (приоритет у Redis)
        all_vars = {**env_vars, **redis_vars}

        # Группируем по секциям
        sections_dict: Dict[str, List[EnvVariable]] = {section: [] for section in self.SECTIONS}
        other_variables: List[EnvVariable] = []  # Для переменных, которые не попали ни в одну секцию

        for key, value in all_vars.items():
            section_name = self.VARIABLE_SECTIONS.get(key, "other")
            is_secret = key in self.SECRET_VARIABLES

            var = EnvVariable(
                key=key,
                value=value if not is_secret else "***",  # Скрываем секретные значения
                description=self._get_variable_description(key),
                type=self._get_variable_type(key, value),
                is_secret=is_secret,
            )

            if section_name in sections_dict:
                sections_dict[section_name].append(var)
            else:
                other_variables.append(var)

        # Добавляем переменные без секции в раздел "other"
        if other_variables:
            sections_dict["other"].extend(other_variables)

        # Создаем объекты секций
        sections = []
        for section_key, variables in sections_dict.items():
            if variables:  # Добавляем только секции с переменными
                sections.append(
                    EnvSection(
                        name=section_key,
                        description=self.SECTIONS[section_key],
                        variables=sorted(variables, key=lambda x: x.key),
                    )
                )

        return sorted(sections, key=lambda x: x.name)

    async def update_variables(self, variables: List[EnvVariable]) -> bool:
        """Обновляет переменные окружения"""

        try:
            # Подготавливаем данные для сохранения
            vars_to_save = {}

            for var in variables:
                # Валидация
                if not var.key or not isinstance(var.key, str):
                    logger.error(f"Неверный ключ переменной: {var.key}")
                    continue

                # Проверяем формат ключа (только буквы, цифры и подчеркивания)
                if not re.match(r"^[A-Z_][A-Z0-9_]*$", var.key):
                    logger.error(f"Неверный формат ключа: {var.key}")
                    continue

                vars_to_save[var.key] = var.value

            if not vars_to_save:
                logger.warning("Нет переменных для сохранения")
                return False

            # Сохраняем в Redis
            success = await self.set_variables_to_redis(vars_to_save)

            if success:
                logger.info(f"Обновлено {len(vars_to_save)} переменных окружения")

            return success

        except Exception as e:
            logger.error(f"Ошибка при обновлении переменных: {e}")
            return False

    async def delete_variable(self, key: str) -> bool:
        """Удаляет переменную окружения"""

        try:
            redis_key = f"{self.redis_prefix}{key}"
            result = await redis.delete(redis_key)

            if result > 0:
                logger.info(f"Переменная {key} удалена")
                return True
            logger.warning(f"Переменная {key} не найдена")
            return False

        except Exception as e:
            logger.error(f"Ошибка при удалении переменной {key}: {e}")
            return False

    async def get_variable(self, key: str) -> Optional[str]:
        """Получает значение конкретной переменной"""

        # Сначала проверяем Redis
        try:
            redis_key = f"{self.redis_prefix}{key}"
            value = await redis.get(redis_key)
            if value:
                return value.decode("utf-8") if isinstance(value, bytes) else str(value)
        except Exception as e:
            logger.error(f"Ошибка при получении переменной {key} из Redis: {e}")

        # Fallback на системное окружение
        return os.getenv(key)

    async def set_variable(self, key: str, value: str) -> bool:
        """Устанавливает значение переменной"""

        try:
            redis_key = f"{self.redis_prefix}{key}"
            await redis.set(redis_key, value)
            logger.info(f"Переменная {key} установлена")
            return True

        except Exception as e:
            logger.error(f"Ошибка при установке переменной {key}: {e}")
            return False


env_manager = EnvManager()
