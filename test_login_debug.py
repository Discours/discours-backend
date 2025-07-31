#!/usr/bin/env python3
"""
Простой тест для отладки авторизации через браузер
"""

import asyncio
import time

from playwright.async_api import async_playwright


async def test_login():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)  # headless=False для отладки
        page = await browser.new_page()

        # Включаем детальное логирование сетевых запросов
        page.on("request", lambda request: print(f"🌐 REQUEST: {request.method} {request.url}"))
        page.on("response", lambda response: print(f"📡 RESPONSE: {response.status} {response.url}"))
        page.on("console", lambda msg: print(f"📝 CONSOLE: {msg.text}"))

        try:
            print("🌐 Открываем страницу входа...")
            await page.goto("http://localhost:3000/login")
            await page.wait_for_load_state("networkidle")

            print("📸 Делаем скриншот страницы входа...")
            await page.screenshot(path="test-results/login_page.png")

            print("🔍 Проверяем элементы формы...")

            # Проверяем наличие полей ввода
            email_field = await page.query_selector('input[type="email"]')
            password_field = await page.query_selector('input[type="password"]')
            submit_button = await page.query_selector('button[type="submit"]')

            print(f"Email поле: {'✅' if email_field else '❌'}")
            print(f"Password поле: {'✅' if password_field else '❌'}")
            print(f"Submit кнопка: {'✅' if submit_button else '❌'}")

            if not all([email_field, password_field, submit_button]):
                print("❌ Не все элементы формы найдены")
                return

            print("🔐 Заполняем форму входа...")
            await page.fill('input[type="email"]', "test_admin@discours.io")
            await page.fill('input[type="password"]', "password123")

            print("📸 Делаем скриншот заполненной формы...")
            await page.screenshot(path="test-results/filled_form.png")

            print("🔄 Нажимаем кнопку входа...")
            await page.click('button[type="submit"]')

            # Ждем немного для обработки
            await asyncio.sleep(5)

            print("📸 Делаем скриншот после нажатия кнопки...")
            await page.screenshot(path="test-results/after_submit.png")

            # Проверяем текущий URL
            current_url = page.url
            print(f"📍 Текущий URL: {current_url}")

            if "/login" in current_url:
                print("❌ Остались на странице входа - авторизация не удалась")

                # Проверяем есть ли ошибка
                error_element = await page.query_selector('.fieldError, .error, [class*="error"]')
                if error_element:
                    error_text = await error_element.text_content()
                    print(f"❌ Ошибка авторизации: {error_text}")
                else:
                    print("❌ Ошибка авторизации не найдена")

                    # Проверяем консоль браузера на наличие ошибок
                    console_messages = await page.evaluate("""
                        () => {
                            return window.console.messages || [];
                        }
                    """)
                    if console_messages:
                        print("📝 Сообщения консоли:")
                        for msg in console_messages:
                            print(f"  {msg}")
            else:
                print("✅ Авторизация прошла успешно!")

                # Проверяем что мы в админ-панели
                if "/admin" in current_url:
                    print("✅ Перенаправлены в админ-панель")

                    # Ждем загрузки админ-панели
                    await page.wait_for_load_state("networkidle")

                    # Проверяем наличие кнопок навигации
                    communities_button = await page.query_selector('button:has-text("Сообщества")')
                    print(f"Кнопка 'Сообщества': {'✅' if communities_button else '❌'}")

                    if communities_button:
                        print("✅ Админ-панель загружена корректно")
                    else:
                        print("❌ Кнопки навигации не найдены")

                        # Делаем скриншот админ-панели
                        await page.screenshot(path="test-results/admin_panel.png")

                        # Получаем HTML для отладки
                        html_content = await page.content()
                        with open("test-results/admin_panel.html", "w", encoding="utf-8") as f:
                            f.write(html_content)
                        print("📄 HTML админ-панели сохранен")
                else:
                    print(f"❌ Неожиданный URL после авторизации: {current_url}")

        except Exception as e:
            print(f"❌ Ошибка в тесте: {e}")
            await page.screenshot(path=f"test-results/error_{int(time.time())}.png")
        finally:
            await browser.close()


if __name__ == "__main__":
    asyncio.run(test_login())
