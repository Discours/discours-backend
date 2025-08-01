#!/usr/bin/env python3
"""
Тест для отладки поиска кнопки удаления
"""

import asyncio
import time

from playwright.async_api import async_playwright


async def test_delete_button():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()

        try:
            print("🌐 Открываем админ-панель...")
            await page.goto("http://localhost:3000/login")
            await page.wait_for_load_state("networkidle")

            print("🔐 Авторизуемся...")
            await page.fill('input[type="email"]', "test_admin@discours.io")
            await page.fill('input[type="password"]', "password123")
            await page.click('button[type="submit"]')

            # Ждем авторизации
            await page.wait_for_url("http://localhost:3000/admin/**", timeout=10000)
            print("✅ Авторизация успешна")

            print("📋 Переходим на страницу сообществ...")
            await page.goto("http://localhost:3000/admin/communities")
            await page.wait_for_load_state("networkidle")

            print("🔍 Ищем таблицу сообществ...")
            await page.wait_for_selector("table", timeout=10000)
            await page.wait_for_selector("table tbody tr", timeout=10000)

            print("📸 Делаем скриншот таблицы...")
            await page.screenshot(path="test-results/communities_table_debug.png")

            # Получаем информацию о всех строках таблицы
            table_info = await page.evaluate("""
                () => {
                    const rows = document.querySelectorAll('table tbody tr');
                    return Array.from(rows).map((row, index) => {
                        const cells = row.querySelectorAll('td');
                        const buttons = row.querySelectorAll('button');
                        return {
                            rowIndex: index,
                            id: cells[0]?.textContent?.trim(),
                            name: cells[1]?.textContent?.trim(),
                            slug: cells[2]?.textContent?.trim(),
                            buttons: Array.from(buttons).map(btn => ({
                                text: btn.textContent?.trim(),
                                className: btn.className,
                                title: btn.title,
                                ariaLabel: btn.getAttribute('aria-label')
                            }))
                        };
                    });
                }
            """)

            print("📋 Информация о таблице:")
            for row in table_info:
                print(f"  Строка {row['rowIndex']}: ID={row['id']}, Name='{row['name']}', Slug='{row['slug']}'")
                print(f"    Кнопки: {row['buttons']}")

            # Ищем строку с "Test Community"
            test_community_row = None
            for row in table_info:
                if "Test Community" in row["name"]:
                    test_community_row = row
                    break

            if test_community_row:
                print(f"✅ Найдена строка с Test Community: {test_community_row}")

                # Пробуем найти кнопку удаления
                row_index = test_community_row["rowIndex"]

                # Способ 1: по классу
                delete_button = await page.query_selector(
                    f"table tbody tr:nth-child({row_index + 1}) button.delete-button"
                )
                print(f"Кнопка по классу delete-button: {'✅' if delete_button else '❌'}")

                # Способ 2: по символу ×
                delete_button = await page.query_selector(
                    f'table tbody tr:nth-child({row_index + 1}) button:has-text("×")'
                )
                print(f"Кнопка по символу ×: {'✅' if delete_button else '❌'}")

                # Способ 3: в последней ячейке
                delete_button = await page.query_selector(
                    f"table tbody tr:nth-child({row_index + 1}) td:last-child button"
                )
                print(f"Кнопка в последней ячейке: {'✅' if delete_button else '❌'}")

                # Способ 4: все кнопки в строке
                buttons = await page.query_selector_all(f"table tbody tr:nth-child({row_index + 1}) button")
                print(f"Всего кнопок в строке: {len(buttons)}")

                for i, btn in enumerate(buttons):
                    text = await btn.text_content()
                    class_name = await btn.get_attribute("class")
                    print(f"  Кнопка {i}: текст='{text}', класс='{class_name}'")

            else:
                print("❌ Строка с Test Community не найдена")

        except Exception as e:
            print(f"❌ Ошибка: {e}")
            await page.screenshot(path=f"test-results/error_{int(time.time())}.png")
        finally:
            await browser.close()


if __name__ == "__main__":
    asyncio.run(test_delete_button())
