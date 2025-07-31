import re
from urllib.parse import quote_plus

from auth.orm import Author
from services.db import local_session


def replace_translit(src: str | None) -> str:
    """
    Транслитерация строки с русского на английский.

    Args:
        src (str | None): Исходная строка или None

    Returns:
        str: Транслитерированная строка или пустая строка, если src None
    """
    if src is None:
        return ""

    # Создаем словарь для замены, так как некоторые русские символы
    # соответствуют нескольким латинским
    translit_dict = {
        "а": "a",
        "б": "b",
        "в": "v",
        "г": "g",
        "д": "d",
        "е": "e",
        "ё": "yo",
        "ж": "zh",
        "з": "z",
        "и": "i",
        "й": "y",
        "к": "k",
        "л": "l",
        "м": "m",
        "н": "n",
        "о": "o",
        "п": "p",
        "р": "r",
        "с": "s",
        "т": "t",
        "у": "u",
        "ф": "f",
        "х": "h",
        "ц": "c",
        "ч": "ch",
        "ш": "sh",
        "щ": "sch",
        "ъ": "",
        "ы": "y",
        "ь": "",
        "э": "e",
        "ю": "yu",
        "я": "ya",
        ".": "-",
    }

    result = ""
    for char in src.lower():
        result += translit_dict.get(char, char)
    return result


def generate_unique_slug(src: str) -> str:
    print("[resolvers.auth] generating slug from: " + src)
    slug = replace_translit(src.lower())
    slug = re.sub("[^0-9a-zA-Z]+", "-", slug)
    if slug != src:
        print("[resolvers.auth] translited name: " + slug)
    c = 1
    with local_session() as session:
        user = session.query(Author).where(Author.slug == slug).first()
        while user:
            user = session.query(Author).where(Author.slug == slug).first()
            slug = slug + "-" + str(c)
            c += 1
        if not user:
            unique_slug = slug
            print("[resolvers.auth] " + unique_slug)
            return quote_plus(unique_slug.replace("'", "")).replace("+", "-")

    # Fallback return если что-то пошло не так
    return quote_plus(slug.replace("'", "")).replace("+", "-")
