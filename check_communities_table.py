#!/usr/bin/env python3
"""
Скрипт для проверки содержимого таблицы сообществ через браузер
"""

import asyncio

from playwright.async_api import async_playwright


async def check_communities_table():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()

        try:
            # Открываем админ-панель
            print("🌐 Открываем админ-панель...")
            await page.goto("http://localhost:3000")
            await page.wait_for_load_state("networkidle")
            await page.wait_for_timeout(3000)

            # Авторизуемся
            print("🔐 Авторизуемся...")
            await page.wait_for_selector('input[type="email"]', timeout=30000)
            await page.fill('input[type="email"]', "test_admin@discours.io")
            await page.fill('input[type="password"]', "password123")
            await page.click('button[type="submit"]')
            await page.wait_for_url("http://localhost:3000/admin/**", timeout=10000)

            # Переходим на страницу сообществ
            print("📋 Переходим на страницу сообществ...")
            await page.wait_for_selector('button:has-text("Сообщества")', timeout=30000)
            await page.click('button:has-text("Сообщества")')
            await page.wait_for_load_state("networkidle")

            # Проверяем содержимое таблицы
            print("🔍 Проверяем содержимое таблицы...")
            await page.wait_for_selector("table", timeout=10000)
            await page.wait_for_selector("table tbody tr", timeout=10000)

            # Получаем все строки таблицы
            communities = await page.evaluate("""
                () => {
                    const rows = document.querySelectorAll('table tbody tr');
                    return Array.from(rows).map(row => {
                        const cells = row.querySelectorAll('td');
                        return {
                            id: cells[0]?.textContent?.trim(),
                            name: cells[1]?.textContent?.trim(),
                            slug: cells[2]?.textContent?.trim(),
                            actions: cells[3]?.textContent?.trim()
                        };
                    });
                }
            """)

            print(f"📊 Найдено {len(communities)} сообществ в таблице:")
            for i, community in enumerate(communities[:10]):  # Показываем первые 10
                print(f"  {i + 1}. ID: {community['id']}, Name: {community['name']}, Slug: {community['slug']}")

            if len(communities) > 10:
                print(f"  ... и еще {len(communities) - 10} сообществ")

            # Ищем конкретное сообщество
            target_slug = "test-admin-community-test-26b67fa4"
            found = any(c["slug"] == target_slug for c in communities)
            print(f"\n🔍 Ищем сообщество '{target_slug}': {'✅ НАЙДЕНО' if found else '❌ НЕ НАЙДЕНО'}")

            # Делаем скриншот
            await page.screenshot(path="test-results/communities_table_debug.png")
            print("📸 Скриншот сохранен в test-results/communities_table_debug.png")

        except Exception as e:
            print(f"❌ Ошибка: {e}")
            await page.screenshot(path="test-results/error_debug.png")
        finally:
            await browser.close()


if __name__ == "__main__":
    asyncio.run(check_communities_table())
