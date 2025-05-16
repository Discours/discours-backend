import re
from urllib.parse import quote_plus

from auth.orm import Author
from services.db import local_session


def replace_translit(src):
    ruchars = "абвгдеёжзийклмнопрстуфхцчшщъыьэюя."
    enchars = [
        "a",
        "b",
        "v",
        "g",
        "d",
        "e",
        "yo",
        "zh",
        "z",
        "i",
        "y",
        "k",
        "l",
        "m",
        "n",
        "o",
        "p",
        "r",
        "s",
        "t",
        "u",
        "f",
        "h",
        "c",
        "ch",
        "sh",
        "sch",
        "",
        "y",
        "'",
        "e",
        "yu",
        "ya",
        "-",
    ]
    return src.translate(str.maketrans(ruchars, enchars))


def generate_unique_slug(src):
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
