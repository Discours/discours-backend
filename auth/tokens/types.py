"""
Типы и константы для системы токенов
"""

from typing import Any, Dict, Literal

# Типы токенов
TokenType = Literal["session", "verification", "oauth_access", "oauth_refresh"]

# TTL по умолчанию для разных типов токенов
DEFAULT_TTL = {
    "session": 30 * 24 * 60 * 60,  # 30 дней
    "verification": 3600,  # 1 час
    "oauth_access": 3600,  # 1 час
    "oauth_refresh": 86400 * 30,  # 30 дней
}

# Размеры батчей для оптимизации Redis операций
BATCH_SIZE = 100  # Размер батча для пакетной обработки токенов
SCAN_BATCH_SIZE = 1000  # Размер батча для SCAN операций

# Общие типы данных
TokenData = Dict[str, Any]
