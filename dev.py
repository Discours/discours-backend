import argparse
import subprocess
from pathlib import Path
from typing import Optional

from granian import Granian
from granian.constants import Interfaces

from utils.logger import root_logger as logger


def check_mkcert_installed() -> Optional[bool]:
    """
    Проверяет, установлен ли инструмент mkcert в системе

    Returns:
        bool: True если mkcert установлен, иначе False

    >>> check_mkcert_installed()  # doctest: +SKIP
    True
    """
    try:
        subprocess.run(["mkcert", "-version"], capture_output=True, check=False)
        return True
    except FileNotFoundError:
        return False


def generate_certificates(domain="localhost", cert_file="localhost.pem", key_file="localhost-key.pem"):
    """
    Генерирует сертификаты с использованием mkcert

    Args:
        domain: Домен для сертификата
        cert_file: Имя файла сертификата
        key_file: Имя файла ключа

    Returns:
        tuple: (cert_file, key_file) пути к созданным файлам

    >>> generate_certificates()  # doctest: +SKIP
    ('localhost.pem', 'localhost-key.pem')
    """
    # Проверяем, существуют ли сертификаты
    if Path(cert_file).exists() and Path(key_file).exists():
        logger.info(f"Сертификаты уже существуют: {cert_file}, {key_file}")
        return cert_file, key_file

    # Проверяем, установлен ли mkcert
    if not check_mkcert_installed():
        logger.error("mkcert не установлен. Установите mkcert с помощью команды:")
        logger.error("  macOS: brew install mkcert")
        logger.error("  Linux: apt install mkcert или эквивалент для вашего дистрибутива")
        logger.error("  Windows: choco install mkcert")
        logger.error("После установки выполните: mkcert -install")
        return None, None

    try:
        # Запускаем mkcert для создания сертификата
        logger.info(f"Создание сертификатов для {domain} с помощью mkcert...")
        result = subprocess.run(
            ["mkcert", "-cert-file", cert_file, "-key-file", key_file, domain],
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode != 0:
            logger.error(f"Ошибка при создании сертификатов: {result.stderr}")
            return None, None

        logger.info(f"Сертификаты созданы: {cert_file}, {key_file}")
        return cert_file, key_file
    except Exception as e:
        logger.error(f"Не удалось создать сертификаты: {e!s}")
        return None, None


def run_server(host="127.0.0.1", port=8000, use_https=False, workers=1, domain="localhost") -> None:
    """
    Запускает сервер Granian с поддержкой HTTPS при необходимости

    Args:
        host: Хост для запуска сервера
        port: Порт для запуска сервера
        use_https: Флаг использования HTTPS
        workers: Количество рабочих процессов
        domain: Домен для сертификата

    >>> run_server(use_https=True)  # doctest: +SKIP
    """
    # Проблема с многопроцессорным режимом - не поддерживает локальные объекты приложений
    # Всегда запускаем в режиме одного процесса для отладки
    if workers > 1:
        logger.warning("Многопроцессорный режим может вызвать проблемы сериализации приложения. Использую 1 процесс.")
        workers = 1

    try:
        if use_https:
            # Генерируем сертификаты с помощью mkcert
            cert_file, key_file = generate_certificates(domain=domain)

            if not cert_file or not key_file:
                logger.error("Не удалось сгенерировать сертификаты для HTTPS")
                return

            logger.info(f"Запуск HTTPS сервера на https://{host}:{port} с использованием Granian")
            # Запускаем Granian сервер с явным указанием ASGI
            server = Granian(
                address=host,
                port=port,
                workers=workers,
                interface=Interfaces.ASGI,
                target="main:app",
                ssl_cert=Path(cert_file),
                ssl_key=Path(key_file),
            )
        else:
            logger.info(f"Запуск HTTP сервера на http://{host}:{port} с использованием Granian")
            server = Granian(
                address=host,
                port=port,
                workers=workers,
                interface=Interfaces.ASGI,
                target="main:app",
            )
        server.serve()
    except Exception as e:
        # В случае проблем с Granian, логируем ошибку
        logger.error(f"Ошибка при запуске Granian: {e!s}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Запуск сервера разработки с поддержкой HTTPS")
    parser.add_argument("--https", action="store_true", help="Использовать HTTPS")
    parser.add_argument("--workers", type=int, default=1, help="Количество рабочих процессов")
    parser.add_argument("--domain", type=str, default="localhost", help="Домен для сертификата")
    parser.add_argument("--port", type=int, default=8000, help="Порт для запуска сервера")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Хост для запуска сервера")

    args = parser.parse_args()

    run_server(host=args.host, port=args.port, use_https=args.https, workers=args.workers, domain=args.domain)
