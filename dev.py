import os
import subprocess
from pathlib import Path
from utils.logger import root_logger as logger
from granian import Granian


def check_mkcert_installed():
    """
    Проверяет, установлен ли инструмент mkcert в системе
    
    Returns:
        bool: True если mkcert установлен, иначе False
        
    >>> check_mkcert_installed()  # doctest: +SKIP
    True
    """
    try:
        subprocess.run(["mkcert", "-version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
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
    if os.path.exists(cert_file) and os.path.exists(key_file):
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
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE,
            text=True
        )
        
        if result.returncode != 0:
            logger.error(f"Ошибка при создании сертификатов: {result.stderr}")
            return None, None
            
        logger.info(f"Сертификаты созданы: {cert_file}, {key_file}")
        return cert_file, key_file
    except Exception as e:
        logger.error(f"Не удалось создать сертификаты: {str(e)}")
        return None, None

def run_server(host="0.0.0.0", port=8000, workers=1):
    """
    Запускает сервер Granian с поддержкой HTTPS при необходимости
    
    Args:
        host: Хост для запуска сервера
        port: Порт для запуска сервера
        use_https: Флаг использования HTTPS
        workers: Количество рабочих процессов
        
    >>> run_server(use_https=True)  # doctest: +SKIP
    """
    # Проблема с многопроцессорным режимом - не поддерживает локальные объекты приложений
    # Всегда запускаем в режиме одного процесса для отладки
    if workers > 1:
        logger.warning("Многопроцессорный режим может вызвать проблемы сериализации приложения. Использую 1 процесс.")
        workers = 1
    
    # При проблемах с ASGI можно попробовать использовать Uvicorn как запасной вариант
    try:
        # Генерируем сертификаты с помощью mkcert
        cert_file, key_file = generate_certificates()
        
        if not cert_file or not key_file:
            logger.error("Не удалось сгенерировать сертификаты для HTTPS")
            return
        
        logger.info(f"Запуск HTTPS сервера на https://{host}:{port} с использованием Granian")
        # Запускаем Granian сервер с явным указанием ASGI
        server = Granian(
            address=host,
            port=port,
            workers=workers,
            interface="asgi",
            target="main:app", 
            ssl_cert=Path(cert_file),
            ssl_key=Path(key_file),
        )
        server.serve()
    except Exception as e:
        # В случае проблем с Granian, пробуем запустить через Uvicorn
        logger.error(f"Ошибка при запуске Granian: {str(e)}")

if __name__ == "__main__":
    run_server() 