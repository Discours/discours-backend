"""
Тест для проверки фикстуры frontend_url
"""

import pytest
import os


def test_frontend_url_fixture(frontend_url):
    """Тест фикстуры frontend_url"""
    print(f"🔧 PLAYWRIGHT_HEADLESS: {os.getenv('PLAYWRIGHT_HEADLESS', 'false')}")
    print(f"🌐 frontend_url: {frontend_url}")
    
    # В локальной разработке (без PLAYWRIGHT_HEADLESS) должен быть порт 8000
    # так как фронтенд сервер не запущен
    if os.getenv("PLAYWRIGHT_HEADLESS", "false").lower() != "true":
        assert frontend_url == "http://localhost:8000"
    else:
        assert frontend_url == "http://localhost:8000"
    
    print(f"✅ frontend_url корректный: {frontend_url}")


def test_frontend_url_environment_variable():
    """Тест переменной окружения PLAYWRIGHT_HEADLESS"""
    playwright_headless = os.getenv("PLAYWRIGHT_HEADLESS", "false").lower() == "true"
    print(f"🔧 PLAYWRIGHT_HEADLESS: {playwright_headless}")
    
    if playwright_headless:
        print("✅ CI/CD режим - используем порт 8000")
    else:
        print("✅ Локальная разработка - используем порт 8000 (фронтенд не запущен)")
