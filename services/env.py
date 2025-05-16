from typing import Dict, List, Optional
from dataclasses import dataclass
from redis import Redis
from settings import REDIS_URL
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
    Менеджер переменных окружения с хранением в Redis
    """

    def __init__(self):
        self.redis = Redis.from_url(REDIS_URL)
        self.prefix = "env:"

    def get_all_variables(self) -> List[EnvSection]:
        """
        Получение всех переменных окружения, сгруппированных по секциям
        """
        try:
            # Получаем все ключи с префиксом env:
            keys = self.redis.keys(f"{self.prefix}*")
            variables: Dict[str, str] = {}

            for key in keys:
                var_key = key.decode("utf-8").replace(self.prefix, "")
                value = self.redis.get(key)
                if value:
                    variables[var_key] = value.decode("utf-8")

            # Группируем переменные по секциям
            sections = [
                EnvSection(
                    name="Авторизация",
                    description="Настройки системы авторизации",
                    variables=[
                        EnvVariable(
                            key="JWT_SECRET",
                            value=variables.get("JWT_SECRET", ""),
                            description="Секретный ключ для JWT токенов",
                            type="string",
                            is_secret=True,
                        ),
                    ],
                ),
                EnvSection(
                    name="Redis",
                    description="Настройки подключения к Redis",
                    variables=[
                        EnvVariable(
                            key="REDIS_URL",
                            value=variables.get("REDIS_URL", ""),
                            description="URL подключения к Redis",
                            type="string",
                        )
                    ],
                ),
                # Добавьте другие секции по необходимости
            ]

            return sections
        except Exception as e:
            logger.error(f"Ошибка получения переменных: {e}")
            return []

    def update_variable(self, key: str, value: str) -> bool:
        """
        Обновление значения переменной
        """
        try:
            full_key = f"{self.prefix}{key}"
            self.redis.set(full_key, value)
            return True
        except Exception as e:
            logger.error(f"Ошибка обновления переменной {key}: {e}")
            return False

    def update_variables(self, variables: List[EnvVariable]) -> bool:
        """
        Массовое обновление переменных
        """
        try:
            pipe = self.redis.pipeline()
            for var in variables:
                full_key = f"{self.prefix}{var.key}"
                pipe.set(full_key, var.value)
            pipe.execute()
            return True
        except Exception as e:
            logger.error(f"Ошибка массового обновления переменных: {e}")
            return False


env_manager = EnvManager()
