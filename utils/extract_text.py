"""
Модуль для обработки HTML-фрагментов
"""

import re
from typing import Optional


def extract_text(html_content: Optional[str]) -> str:
    """
    Извлекает текст из HTML с помощью регулярных выражений.

    Args:
        html_content (Optional[str]): HTML-строка для извлечения текста

    Returns:
        str: Извлеченный текст или пустая строка
    """
    if not html_content:
        return ""

    # Удаляем HTML-теги
    text = re.sub(r"<[^>]+>", " ", html_content)

    # Декодируем HTML-сущности
    text = re.sub(r"&[a-zA-Z]+;", " ", text)

    # Заменяем несколько пробелов на один
    text = re.sub(r"\s+", " ", text).strip()

    return text


def wrap_html_fragment(fragment: str) -> str:
    """
    Оборачивает HTML-фрагмент в полный HTML-документ.

    Args:
        fragment (str): HTML-фрагмент

    Returns:
        str: Полный HTML-документ
    """
    if "<!DOCTYPE html>" in fragment and "<html>" in fragment:
        return fragment

    return f"""<!DOCTYPE html>
<html>
<head>
    <title></title>
</head>
<body>
{fragment}
</body>
</html>"""
