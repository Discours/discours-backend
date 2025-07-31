import os
from dataclasses import dataclass
from typing import ClassVar, Optional

from services.redis import redis
from utils.logger import root_logger as logger


@dataclass
class EnvVariable:
    """Переменная окружения"""

    key: str
    value: str
    description: str
    is_secret: bool = False


@dataclass
class EnvSection:
    """Секция переменных окружения"""

    name: str
    description: str
    variables: list[EnvVariable]


class EnvService:
    """Сервис для работы с переменными окружения"""

    redis_prefix = "env:"

    # Определение секций с их описаниями
    SECTIONS: ClassVar[dict[str, str]] = {
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
    VARIABLE_SECTIONS: ClassVar[dict[str, str]] = {
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
    SECRET_VARIABLES: ClassVar[set[str]] = {
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
        """Инициализация сервиса"""

    def get_variable_description(self, key: str) -> str:
        """Получает описание переменной окружения"""
        descriptions = {
            "DB_URL": "URL подключения к базе данных",
            "DATABASE_URL": "URL подключения к базе данных",
            "POSTGRES_USER": "Пользователь PostgreSQL",
            "POSTGRES_PASSWORD": "Пароль PostgreSQL",
            "POSTGRES_DB": "Имя базы данных PostgreSQL",
            "POSTGRES_HOST": "Хост PostgreSQL",
            "POSTGRES_PORT": "Порт PostgreSQL",
            "JWT_SECRET": "Секретный ключ для JWT токенов",
            "JWT_ALGORITHM": "Алгоритм подписи JWT",
            "JWT_EXPIRATION": "Время жизни JWT токенов",
            "SECRET_KEY": "Секретный ключ приложения",
            "AUTH_SECRET": "Секретный ключ аутентификации",
            "OAUTH_GOOGLE_CLIENT_ID": "Google OAuth Client ID",
            "OAUTH_GOOGLE_CLIENT_SECRET": "Google OAuth Client Secret",
            "OAUTH_GITHUB_CLIENT_ID": "GitHub OAuth Client ID",
            "OAUTH_GITHUB_CLIENT_SECRET": "GitHub OAuth Client Secret",
            "REDIS_URL": "URL подключения к Redis",
            "REDIS_HOST": "Хост Redis",
            "REDIS_PORT": "Порт Redis",
            "REDIS_PASSWORD": "Пароль Redis",
            "REDIS_DB": "Номер базы данных Redis",
            "SEARCH_API_KEY": "API ключ для поиска",
            "ELASTICSEARCH_URL": "URL Elasticsearch",
            "SEARCH_INDEX": "Индекс поиска",
            "GOOGLE_ANALYTICS_ID": "Google Analytics ID",
            "SENTRY_DSN": "Sentry DSN",
            "SMTP_HOST": "SMTP сервер",
            "SMTP_PORT": "Порт SMTP",
            "SMTP_USER": "Пользователь SMTP",
            "SMTP_PASSWORD": "Пароль SMTP",
            "EMAIL_FROM": "Email отправителя",
            "CORS_ORIGINS": "Разрешенные CORS источники",
            "ALLOWED_HOSTS": "Разрешенные хосты",
            "SECURE_SSL_REDIRECT": "Принудительное SSL перенаправление",
            "SESSION_COOKIE_SECURE": "Безопасные cookies сессий",
            "CSRF_COOKIE_SECURE": "Безопасные CSRF cookies",
            "LOG_LEVEL": "Уровень логирования",
            "LOG_FORMAT": "Формат логов",
            "LOG_FILE": "Файл логов",
            "DEBUG": "Режим отладки",
            "FEATURE_REGISTRATION": "Включить регистрацию",
            "FEATURE_COMMENTS": "Включить комментарии",
            "FEATURE_ANALYTICS": "Включить аналитику",
            "FEATURE_SEARCH": "Включить поиск",
        }
        return descriptions.get(key, f"Переменная окружения {key}")

    async def get_variables_from_redis(self) -> dict[str, str]:
        """Получает переменные из Redis"""
        try:
            keys = await redis.keys(f"{self.redis_prefix}*")
            if not keys:
                return {}

            redis_vars: dict[str, str] = {}
            for key in keys:
                var_key = key.replace(self.redis_prefix, "")
                value = await redis.get(key)
                if value:
                    redis_vars[var_key] = str(value)

            return redis_vars
        except Exception:
            return {}

    async def set_variables_to_redis(self, variables: dict[str, str]) -> bool:
        """Сохраняет переменные в Redis"""
        try:
            for key, value in variables.items():
                await redis.set(f"{self.redis_prefix}{key}", value)
            return True
        except Exception:
            return False

    def get_variables_from_env(self) -> dict[str, str]:
        """Получает переменные из системного окружения"""
        env_vars = {}

        # Получаем все переменные известные системе
        for key in self.VARIABLE_SECTIONS:
            value = os.getenv(key)
            if value is not None:
                env_vars[key] = value

        # Получаем дополнительные переменные окружения
        env_vars.update(
            {
                env_key: env_value
                for env_key, env_value in os.environ.items()
                if any(env_key.startswith(prefix) for prefix in ["APP_", "SITE_", "FEATURE_", "OAUTH_"])
            }
        )

        return env_vars

    async def get_all_variables(self) -> list[EnvSection]:
        """Получает все переменные окружения, сгруппированные по секциям"""
        # Получаем переменные из Redis и системного окружения
        redis_vars = await self.get_variables_from_redis()
        env_vars = self.get_variables_from_env()

        # Объединяем переменные (Redis имеет приоритет)
        all_vars = {**env_vars, **redis_vars}

        # Группируем по секциям
        sections_dict: dict[str, list[EnvVariable]] = {section: [] for section in self.SECTIONS}
        other_variables: list[EnvVariable] = []  # Для переменных, которые не попали ни в одну секцию

        for key, value in all_vars.items():
            is_secret = key in self.SECRET_VARIABLES
            description = self.get_variable_description(key)

            # Скрываем значение секретных переменных
            display_value = "***" if is_secret else value

            env_var = EnvVariable(
                key=key,
                value=display_value,
                description=description,
                is_secret=is_secret,
            )

            # Определяем секцию для переменной
            section = self.VARIABLE_SECTIONS.get(key, "other")
            if section in sections_dict:
                sections_dict[section].append(env_var)
            else:
                other_variables.append(env_var)

        # Создаем объекты секций
        sections = []
        for section_name, section_description in self.SECTIONS.items():
            variables = sections_dict.get(section_name, [])
            if variables:  # Добавляем только непустые секции
                sections.append(EnvSection(name=section_name, description=section_description, variables=variables))

        # Добавляем секцию "other" если есть переменные
        if other_variables:
            sections.append(EnvSection(name="other", description="Прочие настройки", variables=other_variables))

        return sorted(sections, key=lambda x: x.name)

    async def update_variables(self, variables: list[EnvVariable]) -> bool:
        """Обновляет переменные окружения"""
        try:
            # Подготавливаем переменные для сохранения
            vars_dict = {}
            for var in variables:
                if not var.is_secret or var.value != "***":
                    vars_dict[var.key] = var.value

            # Сохраняем в Redis
            return await self.set_variables_to_redis(vars_dict)
        except Exception:
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


env_manager = EnvService()
