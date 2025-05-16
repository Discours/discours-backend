"""
Модуль для обработки HTML-фрагментов
"""

import trafilatura


def extract_text(html: str) -> str:
    """
    Извлекает текст из HTML-фрагмента.

    Args:
        html: HTML-фрагмент

    Returns:
        str: Текст из HTML-фрагмента
    """
    return trafilatura.extract(
        wrap_html_fragment(html),
        include_comments=False,
        include_tables=False,
        include_images=False,
        include_formatting=False,
    )


def wrap_html_fragment(fragment: str) -> str:
    """
    Оборачивает HTML-фрагмент в полную HTML-структуру для корректной обработки.

    Args:
        fragment: HTML-фрагмент для обработки

    Returns:
        str: Полный HTML-документ

    Example:
        >>> wrap_html_fragment("<p>Текст параграфа</p>")
        '<!DOCTYPE html><html><head><meta charset="utf-8"></head><body><p>Текст параграфа</p></body></html>'
    """
    if not fragment or not fragment.strip():
        return fragment

    # Проверяем, является ли контент полным HTML-документом
    is_full_html = fragment.strip().startswith("<!DOCTYPE") or fragment.strip().startswith("<html")

    # Если это фрагмент, оборачиваем его в полный HTML-документ
    if not is_full_html:
        return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title></title>
</head>
<body>
{fragment}
</body>
</html>"""

    return fragment
