from typing import Dict, List, Optional, Set
from dataclasses import dataclass
import os
import re
from pathlib import Path
from redis import Redis
from settings import REDIS_URL, ROOT_DIR
from utils.logger import root_logger as logger


@dataclass
class EnvVariable:
    key: str
    value: str
    description: Optional[str] = None
    type: str = "string"
    is_secret: bool = False


@dataclass
class EnvSection:
    name: str
    variables: List[EnvVariable]
    description: Optional[str] = None


class EnvManager:
    """
    Менеджер переменных окружения с хранением в Redis и синхронизацией с .env файлом
    """

    # Стандартные переменные окружения, которые следует исключить
    EXCLUDED_ENV_VARS: Set[str] = {
        "PATH", "SHELL", "USER", "HOME", "PWD", "TERM", "LANG", 
        "PYTHONPATH", "_", "TMPDIR", "TERM_PROGRAM", "TERM_SESSION_ID",
        "XPC_SERVICE_NAME", "XPC_FLAGS", "SHLVL", "SECURITYSESSIONID",
        "LOGNAME", "OLDPWD", "ZSH", "PAGER", "LESS", "LC_CTYPE", "LSCOLORS",
        "SSH_AUTH_SOCK", "DISPLAY", "COLORTERM", "EDITOR", "VISUAL",
        "PYTHONDONTWRITEBYTECODE", "VIRTUAL_ENV", "PYTHONUNBUFFERED"
    }

    # Секции для группировки переменных
    SECTIONS = {
        "AUTH": {
            "pattern": r"^(JWT|AUTH|SESSION|OAUTH|GITHUB|GOOGLE|FACEBOOK)_",
            "name": "Авторизация",
            "description": "Настройки системы авторизации"
        },
        "DATABASE": {
            "pattern": r"^(DB|DATABASE|POSTGRES|MYSQL|SQL)_",
            "name": "База данных",
            "description": "Настройки подключения к базам данных"
        },
        "CACHE": {
            "pattern": r"^(REDIS|CACHE|MEMCACHED)_",
            "name": "Кэширование",
            "description": "Настройки систем кэширования"
        },
        "SEARCH": {
            "pattern": r"^(ELASTIC|SEARCH|OPENSEARCH)_",
            "name": "Поиск",
            "description": "Настройки поисковых систем"
        },
        "APP": {
            "pattern": r"^(APP|PORT|HOST|DEBUG|DOMAIN|ENVIRONMENT|ENV|FRONTEND)_",
            "name": "Приложение",
            "description": "Основные настройки приложения"
        },
        "LOGGING": {
            "pattern": r"^(LOG|LOGGING|SENTRY|GLITCH|GLITCHTIP)_",
            "name": "Логирование",
            "description": "Настройки логирования и мониторинга"
        },
        "EMAIL": {
            "pattern": r"^(MAIL|EMAIL|SMTP)_",
            "name": "Электронная почта",
            "description": "Настройки отправки электронной почты"
        },
        "ANALYTICS": {
            "pattern": r"^(GA|GOOGLE_ANALYTICS|ANALYTICS)_",
            "name": "Аналитика",
            "description": "Настройки систем аналитики"
        },
    }

    # Переменные, которые следует всегда помечать как секретные
    SECRET_VARS_PATTERNS = [
        r".*TOKEN.*", r".*SECRET.*", r".*PASSWORD.*", r".*KEY.*", 
        r".*PWD.*", r".*PASS.*", r".*CRED.*"
    ]

    def __init__(self):
        self.redis = Redis.from_url(REDIS_URL)
        self.prefix = "env:"
        self.env_file_path = os.path.join(ROOT_DIR, '.env')

    def get_all_variables(self) -> List[EnvSection]:
        """
        Получение всех переменных окружения, сгруппированных по секциям
        """
        try:
            # Получаем все переменные окружения из системы
            system_env = self._get_system_env_vars()

            # Получаем переменные из .env файла, если он существует
            dotenv_vars = self._get_dotenv_vars()

            # Получаем все переменные из Redis
            redis_vars = self._get_redis_env_vars()

            # Объединяем переменные, при этом redis_vars имеют наивысший приоритет,
            # за ними следуют переменные из .env, затем системные
            env_vars = {**system_env, **dotenv_vars, **redis_vars}

            # Группируем переменные по секциям
            return self._group_variables_by_sections(env_vars)
        except Exception as e:
            logger.error(f"Ошибка получения переменных: {e}")
            return []

    def _get_system_env_vars(self) -> Dict[str, str]:
        """
        Получает переменные окружения из системы, исключая стандартные
        """
        env_vars = {}
        for key, value in os.environ.items():
            # Пропускаем стандартные переменные
            if key in self.EXCLUDED_ENV_VARS:
                continue
            # Пропускаем переменные с пустыми значениями
            if not value:
                continue
            env_vars[key] = value
        return env_vars

    def _get_dotenv_vars(self) -> Dict[str, str]:
        """
        Получает переменные из .env файла, если он существует
        """
        env_vars = {}
        if os.path.exists(self.env_file_path):
            try:
                with open(self.env_file_path, 'r') as f:
                    for line in f:
                        line = line.strip()
                        # Пропускаем пустые строки и комментарии
                        if not line or line.startswith('#'):
                            continue
                        # Разделяем строку на ключ и значение
                        if '=' in line:
                            key, value = line.split('=', 1)
                            key = key.strip()
                            value = value.strip()
                            # Удаляем кавычки, если они есть
                            if value.startswith('"') and value.endswith('"'):
                                value = value[1:-1]
                            env_vars[key] = value
            except Exception as e:
                logger.error(f"Ошибка чтения .env файла: {e}")
        return env_vars

    def _get_redis_env_vars(self) -> Dict[str, str]:
        """
        Получает переменные окружения из Redis
        """
        redis_vars = {}
        try:
            # Получаем все ключи с префиксом env:
            keys = self.redis.keys(f"{self.prefix}*")
            for key in keys:
                var_key = key.decode("utf-8").replace(self.prefix, "")
                value = self.redis.get(key)
                if value:
                    redis_vars[var_key] = value.decode("utf-8")
        except Exception as e:
            logger.error(f"Ошибка получения переменных из Redis: {e}")
        return redis_vars

    def _is_secret_variable(self, key: str) -> bool:
        """
        Проверяет, является ли переменная секретной
        """
        key_upper = key.upper()
        return any(re.match(pattern, key_upper) for pattern in self.SECRET_VARS_PATTERNS)

    def _determine_variable_type(self, value: str) -> str:
        """
        Определяет тип переменной на основе ее значения
        """
        if value.lower() in ('true', 'false'):
            return "boolean"
        if value.isdigit():
            return "integer"
        if re.match(r"^\d+\.\d+$", value):
            return "float"
        # Проверяем на JSON объект или массив
        if (value.startswith('{') and value.endswith('}')) or (value.startswith('[') and value.endswith(']')):
            return "json"
        # Проверяем на URL
        if value.startswith(('http://', 'https://', 'redis://', 'postgresql://')):
            return "url"
        return "string"

    def _group_variables_by_sections(self, variables: Dict[str, str]) -> List[EnvSection]:
        """
        Группирует переменные по секциям
        """
        # Создаем словарь для группировки переменных
        sections_dict = {section: [] for section in self.SECTIONS}
        other_variables = []  # Для переменных, которые не попали ни в одну секцию

        # Распределяем переменные по секциям
        for key, value in variables.items():
            is_secret = self._is_secret_variable(key)
            var_type = self._determine_variable_type(value)
            
            var = EnvVariable(
                key=key,
                value=value,
                type=var_type,
                is_secret=is_secret
            )
            
            # Определяем секцию для переменной
            placed = False
            for section_id, section_config in self.SECTIONS.items():
                if re.match(section_config["pattern"], key, re.IGNORECASE):
                    sections_dict[section_id].append(var)
                    placed = True
                    break
            
            # Если переменная не попала ни в одну секцию
            if not placed:
                other_variables.append(var)

        # Формируем результат
        result = []
        for section_id, variables in sections_dict.items():
            if variables:  # Добавляем только непустые секции
                section_config = self.SECTIONS[section_id]
                result.append(
                    EnvSection(
                        name=section_config["name"],
                        description=section_config["description"],
                        variables=variables
                    )
                )
        
        # Добавляем прочие переменные, если они есть
        if other_variables:
            result.append(
                EnvSection(
                    name="Прочие переменные",
                    description="Переменные, не вошедшие в основные категории",
                    variables=other_variables
                )
            )
        
        return result

    def update_variable(self, key: str, value: str) -> bool:
        """
        Обновление значения переменной в Redis и .env файле
        """
        try:
            # Сохраняем в Redis
            full_key = f"{self.prefix}{key}"
            self.redis.set(full_key, value)
            
            # Обновляем значение в .env файле
            self._update_dotenv_var(key, value)
            
            # Обновляем переменную в текущем процессе
            os.environ[key] = value
            
            return True
        except Exception as e:
            logger.error(f"Ошибка обновления переменной {key}: {e}")
            return False

    def _update_dotenv_var(self, key: str, value: str) -> bool:
        """
        Обновляет переменную в .env файле
        """
        try:
            # Если файл .env не существует, создаем его
            if not os.path.exists(self.env_file_path):
                with open(self.env_file_path, 'w') as f:
                    f.write(f"{key}={value}\n")
                return True
            
            # Если файл существует, читаем его содержимое
            lines = []
            found = False
            
            with open(self.env_file_path, 'r') as f:
                for line in f:
                    if line.strip() and not line.strip().startswith('#'):
                        if line.strip().startswith(f"{key}="):
                            # Экранируем значение, если необходимо
                            if ' ' in value or ',' in value or '"' in value or "'" in value:
                                escaped_value = f'"{value}"'
                            else:
                                escaped_value = value
                            lines.append(f"{key}={escaped_value}\n")
                            found = True
                        else:
                            lines.append(line)
                    else:
                        lines.append(line)
            
            # Если переменной не было в файле, добавляем ее
            if not found:
                # Экранируем значение, если необходимо
                if ' ' in value or ',' in value or '"' in value or "'" in value:
                    escaped_value = f'"{value}"'
                else:
                    escaped_value = value
                lines.append(f"{key}={escaped_value}\n")
            
            # Записываем обновленный файл
            with open(self.env_file_path, 'w') as f:
                f.writelines(lines)
            
            return True
        except Exception as e:
            logger.error(f"Ошибка обновления .env файла: {e}")
            return False

    def update_variables(self, variables: List[EnvVariable]) -> bool:
        """
        Массовое обновление переменных
        """
        try:
            # Обновляем переменные в Redis
            pipe = self.redis.pipeline()
            for var in variables:
                full_key = f"{self.prefix}{var.key}"
                pipe.set(full_key, var.value)
            pipe.execute()
            
            # Обновляем переменные в .env файле
            for var in variables:
                self._update_dotenv_var(var.key, var.value)
                
                # Обновляем переменную в текущем процессе
                os.environ[var.key] = var.value
                
            return True
        except Exception as e:
            logger.error(f"Ошибка массового обновления переменных: {e}")
            return False


env_manager = EnvManager()
