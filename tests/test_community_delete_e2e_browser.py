"""
Настоящий E2E тест для удаления сообщества через браузер.

Использует Playwright для автоматизации браузера и тестирует:
1. Запуск сервера
2. Открытие админ-панели в браузере
3. Авторизацию
4. Переход на страницу сообществ
5. Удаление сообщества
6. Проверку результата
"""

import pytest
import time
import asyncio
from playwright.async_api import async_playwright, Page, Browser, BrowserContext
import subprocess
import signal
import os
import sys
import requests
from dotenv import load_dotenv

# Загружаем переменные окружения для E2E тестов
load_dotenv()

# Добавляем путь к проекту для импорта
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from auth.orm import Author
from orm.community import Community, CommunityAuthor
from services.db import local_session


class TestCommunityDeleteE2EBrowser:
    """E2E тесты для удаления сообщества через браузер"""

    @pytest.fixture
    async def browser_setup(self):
        """Настройка браузера и запуск серверов"""
        # Запускаем бэкенд сервер в фоне
        backend_process = None
        frontend_process = None
        try:
            # Проверяем, не запущен ли уже сервер
            try:
                response = requests.get("http://localhost:8000/", timeout=2)
                if response.status_code == 200:
                    print("✅ Бэкенд сервер уже запущен")
                    backend_running = True
                else:
                    backend_running = False
            except:
                backend_running = False

            if not backend_running:
                # Запускаем бэкенд сервер в CI/CD среде
                print("🔄 Запускаем бэкенд сервер...")
                try:
                    # В CI/CD используем uv run python
                    backend_process = subprocess.Popen(
                        ["uv", "run", "python", "dev.py"],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                    )

                    # Ждем запуска бэкенда
                    print("⏳ Ждем запуска бэкенда...")
                    for i in range(20):  # Ждем максимум 20 секунд
                        try:
                            response = requests.get("http://localhost:8000/", timeout=2)
                            if response.status_code == 200:
                                print("✅ Бэкенд сервер запущен")
                                break
                        except:
                            pass
                        await asyncio.sleep(1)
                    else:
                        # Если сервер не запустился, выводим логи и завершаем тест
                        print("❌ Бэкенд сервер не запустился за 20 секунд")
                        
                        # Получаем логи процесса
                        if backend_process:
                            stdout, stderr = backend_process.communicate()
                            print(f"📋 STDOUT: {stdout.decode()}")
                            print(f"📋 STDERR: {stderr.decode()}")
                        
                        raise Exception("Бэкенд сервер не запустился за 20 секунд")
                        
                except Exception as e:
                    print(f"❌ Ошибка запуска сервера: {e}")
                    raise Exception(f"Не удалось запустить бэкенд сервер: {e}")

            # Проверяем фронтенд
            try:
                response = requests.get("http://localhost:8000", timeout=2)
                if response.status_code == 200:
                    print("✅ Фронтенд сервер уже запущен")
                    frontend_running = True
                else:
                    frontend_running = False
            except:
                frontend_running = False

            if not frontend_running:
                # Проверяем, находимся ли мы в CI/CD окружении
                is_ci = os.getenv("PLAYWRIGHT_HEADLESS", "false").lower() == "true"
                
                if is_ci:
                    print("🔧 CI/CD окружение - фронтенд собран и обслуживается бэкендом")
                    # В CI/CD фронтенд уже собран и обслуживается бэкендом на порту 8000
                    try:
                        response = requests.get("http://localhost:8000/", timeout=2)
                        if response.status_code == 200:
                            print("✅ Бэкенд готов обслуживать фронтенд")
                            frontend_running = True
                            frontend_process = None
                        else:
                            print(f"⚠️ Бэкенд вернул статус {response.status_code}")
                            frontend_process = None
                    except Exception as e:
                        print(f"⚠️ Не удалось проверить бэкенд: {e}")
                        frontend_process = None
                else:
                    # Локальная разработка - запускаем фронтенд сервер
                    print("🔄 Запускаем фронтенд сервер...")
                    try:
                        frontend_process = subprocess.Popen(
                            ["npm", "run", "dev"],
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                        )
                        
                        # Ждем запуска фронтенда
                        print("⏳ Ждем запуска фронтенда...")
                        for i in range(15):  # Ждем максимум 15 секунд
                            try:
                                # В локальной разработке фронтенд работает на порту 3000
                                response = requests.get("http://localhost:3000", timeout=2)
                                if response.status_code == 200:
                                    print("✅ Фронтенд сервер запущен")
                                    break
                            except:
                                pass
                            await asyncio.sleep(1)
                        else:
                            # Если фронтенд не запустился, выводим логи
                            print("❌ Фронтенд сервер не запустился за 15 секунд")
                            
                            # Получаем логи процесса
                            if frontend_process:
                                stdout, stderr = frontend_process.communicate()
                                print(f"📋 STDOUT: {stdout.decode()}")
                                print(f"📋 STDERR: {stderr.decode()}")
                            
                            print("⚠️ Продолжаем тест без фронтенда (только API тесты)")
                            frontend_process = None
                            
                    except Exception as e:
                        print(f"⚠️ Не удалось запустить фронтенд сервер: {e}")
                        print("🔄 Продолжаем тест без фронтенда (только API тесты)")
                        frontend_process = None

            # Запускаем браузер
            print("🔄 Запускаем браузер...")
            playwright = await async_playwright().start()
            
            # Определяем headless режим из переменной окружения
            headless_mode = os.getenv("PLAYWRIGHT_HEADLESS", "false").lower() == "true"
            print(f"🔧 Headless режим: {headless_mode}")
            
            browser = await playwright.chromium.launch(
                headless=headless_mode,  # Используем переменную окружения для CI/CD
                args=["--no-sandbox", "--disable-dev-shm-usage"]
            )
            context = await browser.new_context()
            page = await context.new_page()

            yield {
                "playwright": playwright,
                "browser": browser,
                "context": context,
                "page": page,
                "backend_process": backend_process,
                "frontend_process": frontend_process
            }

        finally:
            # Очистка
            print("🧹 Очистка ресурсов...")
            if frontend_process:
                frontend_process.terminate()
                try:
                    frontend_process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    frontend_process.kill()
            if backend_process:
                backend_process.terminate()
                try:
                    backend_process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    backend_process.kill()

            try:
                if 'browser' in locals():
                    await browser.close()
                if 'playwright' in locals():
                    await playwright.stop()
            except Exception as e:
                print(f"⚠️ Ошибка при закрытии браузера: {e}")

    @pytest.fixture
    def test_community_for_browser(self, db_session, test_users):
        """Создает тестовое сообщество для удаления через браузер"""
        community = Community(
            id=888,
            name="Browser Test Community",
            slug="browser-test-community",
            desc="Test community for browser E2E tests",
            created_by=test_users[0].id,
            created_at=int(time.time())
        )
        db_session.add(community)
        db_session.commit()
        return community

    @pytest.fixture
    def admin_user_for_browser(self, db_session, test_users, test_community_for_browser):
        """Создает администратора с правами на удаление"""
        user = test_users[0]

        # Создаем CommunityAuthor с правами администратора
        ca = CommunityAuthor(
            community_id=test_community_for_browser.id,
            author_id=user.id,
            roles="admin,editor,author"
        )
        db_session.add(ca)
        db_session.commit()

        return user

    async def test_community_delete_browser_workflow(self, browser_setup, test_users, frontend_url):
        """Полный E2E тест удаления сообщества через браузер"""

        page = browser_setup["page"]

        # Серверы уже запущены в browser_setup фикстуре
        print("✅ Серверы запущены и готовы к тестированию")

        # Используем существующее сообщество для тестирования удаления
        # Берем первое доступное сообщество из БД
        test_community_name = "Test Editor Community"  # Существующее сообщество из БД
        test_community_slug = "test-editor-community-test-902f937f"  # Конкретный slug для удаления

        print(f"🔍 Будем тестировать удаление сообщества: {test_community_name}")

        try:
            # 1. Открываем админ-панель
            print(f"🌐 Открываем админ-панель на {frontend_url}...")
            await page.goto(frontend_url)

            # Ждем загрузки страницы и JavaScript
            await page.wait_for_load_state("networkidle")
            await page.wait_for_load_state("domcontentloaded")

            # Дополнительное ожидание для загрузки React приложения
            await page.wait_for_timeout(3000)
            print("✅ Страница загружена")

            # 2. Авторизуемся через форму входа
            print("🔐 Авторизуемся через форму входа...")

            # Ждем появления формы входа с увеличенным таймаутом
            await page.wait_for_selector('input[type="email"]', timeout=30000)
            await page.wait_for_selector('input[type="password"]', timeout=10000)

            # Заполняем форму входа
            await page.fill('input[type="email"]', 'test_admin@discours.io')
            await page.fill('input[type="password"]', 'password123')

            # Нажимаем кнопку входа
            await page.click('button[type="submit"]')

            # Ждем успешной авторизации (редирект на главную страницу админки)
            await page.wait_for_url(f"{frontend_url}/admin/**", timeout=10000)
            print("✅ Авторизация успешна")

            # Проверяем что мы действительно в админ-панели
            await page.wait_for_selector('button:has-text("Сообщества")', timeout=30000)
            print("✅ Админ-панель загружена")

            # 3. Переходим на страницу сообществ
            print("📋 Переходим на страницу сообществ...")

            # Ищем кнопку "Сообщества" в навигации
            await page.wait_for_selector('button:has-text("Сообщества")', timeout=30000)
            await page.click('button:has-text("Сообщества")')

            # Ждем загрузки страницы сообществ
            await page.wait_for_load_state("networkidle")
            print("✅ Страница сообществ загружена")

            # Проверяем что мы на правильной странице
            current_url = page.url
            print(f"📍 Текущий URL: {current_url}")

            if "/admin/communities" not in current_url:
                print("⚠️ Не на странице управления сообществами, переходим...")
                await page.goto(f"{frontend_url}/admin/communities")
                await page.wait_for_load_state("networkidle")
                print("✅ Перешли на страницу управления сообществами")

            # 4. Ищем наше тестовое сообщество
            print(f"🔍 Ищем сообщество: {test_community_name}")

            # Сначала делаем скриншот для отладки
            await page.screenshot(path="test-results/debug_page.png")
            print("📸 Скриншот страницы сохранен для отладки")

            # Получаем HTML страницы для отладки
            page_html = await page.content()
            print(f"📄 Размер HTML страницы: {len(page_html)} символов")
            
            # Ищем любые таблицы на странице
            tables = await page.query_selector_all('table')
            print(f"🔍 Найдено таблиц на странице: {len(tables)}")
            
            # Ищем другие возможные селекторы для списка сообществ
            possible_selectors = [
                'table',
                '[data-testid="communities-table"]',
                '.communities-table',
                '.communities-list',
                '[class*="table"]',
                '[class*="list"]'
            ]
            
            found_element = None
            for selector in possible_selectors:
                try:
                    element = await page.wait_for_selector(selector, timeout=2000)
                    if element:
                        print(f"✅ Найден элемент с селектором: {selector}")
                        found_element = element
                        break
                except:
                    continue
            
            if not found_element:
                print("❌ Не найдена таблица сообществ")
                print("🔍 Доступные элементы на странице:")
                
                # Получаем список всех элементов с классами
                elements_with_classes = await page.evaluate("""
                    () => {
                        const elements = document.querySelectorAll('*[class]');
                        const classes = {};
                        elements.forEach(el => {
                            const classList = Array.from(el.classList);
                            classList.forEach(cls => {
                                if (!classes[cls]) classes[cls] = 0;
                                classes[cls]++;
                            });
                        });
                        return classes;
                    }
                """)
                print(f"📋 Классы элементов: {elements_with_classes}")
                
                raise Exception("Не найдена таблица сообществ на странице")

            print("✅ Элемент со списком сообществ найден")

            # Ждем загрузки данных в найденном элементе
            # Используем найденный элемент вместо жестко заданного селектора
            print("⏳ Ждем загрузки данных...")
            
            # Ждем дольше для загрузки данных
            await page.wait_for_timeout(5000)
            
            try:
                # Ищем строки в найденном элементе
                rows = await found_element.query_selector_all('tr, [class*="row"], [class*="item"], [class*="card"], [class*="community"]')
                if rows:
                    print(f"✅ Найдено строк в элементе: {len(rows)}")
                    
                    # Выводим содержимое первых нескольких строк для отладки
                    for i, row in enumerate(rows[:3]):
                        try:
                            text = await row.text_content()
                            print(f"📋 Строка {i+1}: {text[:100]}...")
                        except:
                            print(f"📋 Строка {i+1}: [не удалось прочитать]")
                else:
                    print("⚠️ Строки данных не найдены")
                    
                    # Пробуем найти любые элементы с текстом
                    all_elements = await found_element.query_selector_all('*')
                    print(f"🔍 Всего элементов в найденном элементе: {len(all_elements)}")
                    
                    # Ищем элементы с текстом
                    text_elements = []
                    for elem in all_elements[:10]:  # Проверяем первые 10
                        try:
                            text = await elem.text_content()
                            if text and text.strip() and len(text.strip()) > 3:
                                text_elements.append(text.strip()[:50])
                        except:
                            pass
                    
                    print(f"📋 Элементы с текстом: {text_elements}")
                    
            except Exception as e:
                print(f"⚠️ Ошибка при поиске строк: {e}")
            
            print("✅ Данные загружены")

            # Ищем строку с нашим конкретным сообществом по slug
            # Используем найденный элемент и ищем по тексту
            community_row = None
            
            # Ищем в найденном элементе
            try:
                community_row = await found_element.query_selector(f'*:has-text("{test_community_slug}")')
                if community_row:
                    print(f"✅ Найдено сообщество {test_community_slug} в элементе")
                else:
                    # Если не найдено, ищем по всему содержимому
                    print(f"🔍 Ищем сообщество {test_community_slug} по всему содержимому...")
                    all_text = await found_element.text_content()
                    if test_community_slug in all_text:
                        print(f"✅ Текст сообщества {test_community_slug} найден в содержимом")
                        # Ищем родительский элемент, содержащий этот текст
                        community_row = await found_element.query_selector(f'*:has-text("{test_community_slug}")')
                    else:
                        print(f"❌ Сообщество {test_community_slug} не найдено в содержимом")
            except Exception as e:
                print(f"⚠️ Ошибка при поиске сообщества: {e}")

            if not community_row:
                # Делаем скриншот для отладки
                await page.screenshot(path="test-results/communities_table.png")

                # Получаем список всех сообществ в таблице
                all_communities = await page.evaluate("""
                    () => {
                        const rows = document.querySelectorAll('table tbody tr');
                        return Array.from(rows).map(row => {
                            const cells = row.querySelectorAll('td');
                            return {
                                id: cells[0]?.textContent?.trim(),
                                name: cells[1]?.textContent?.trim(),
                                slug: cells[2]?.textContent?.trim()
                            };
                        });
                    }
                """)

                print(f"📋 Найденные сообщества в таблице: {all_communities}")
                raise Exception(f"Сообщество {test_community_name} не найдено в таблице")

            print(f"✅ Найдено сообщество: {test_community_name}")

            # 5. Удаляем сообщество
            print("🗑️ Удаляем сообщество...")

            # Ищем кнопку удаления в строке с нашим конкретным сообществом
            # Кнопка удаления содержит символ '×' и находится в последней ячейке
            delete_button = await page.wait_for_selector(
                f'table tbody tr:has-text("{test_community_slug}") button:has-text("×")',
                timeout=10000
            )

            if not delete_button:
                # Альтернативный поиск - найти кнопку в последней ячейке строки
                delete_button = await page.wait_for_selector(
                    f'table tbody tr:has-text("{test_community_slug}") td:last-child button',
                    timeout=10000
                )

            if not delete_button:
                # Еще один способ - найти кнопку по CSS модулю классу
                delete_button = await page.wait_for_selector(
                    f'table tbody tr:has-text("{test_community_slug}") button[class*="delete-button"]',
                    timeout=10000
                )

            if not delete_button:
                # Делаем скриншот для отладки
                await page.screenshot(path="test-results/delete_button_not_found.png")
                raise Exception("Кнопка удаления не найдена")

            print("✅ Кнопка удаления найдена")

            # Нажимаем кнопку удаления
            await delete_button.click()

            # Ждем появления диалога подтверждения
            # Модальное окно использует CSS модули, поэтому ищем по backdrop
            await page.wait_for_selector('[class*="backdrop"]', timeout=10000)

            # Подтверждаем удаление
            # Ищем кнопку "Удалить" в модальном окне
            confirm_button = await page.wait_for_selector(
                '[class*="backdrop"] button:has-text("Удалить")',
                timeout=10000
            )

            if not confirm_button:
                # Альтернативный поиск
                confirm_button = await page.wait_for_selector(
                    '[class*="modal"] button:has-text("Удалить")',
                    timeout=10000
                )

            if not confirm_button:
                # Еще один способ - найти кнопку с variant="danger"
                confirm_button = await page.wait_for_selector(
                    '[class*="backdrop"] button[class*="danger"]',
                    timeout=10000
                )

            if not confirm_button:
                # Делаем скриншот для отладки
                await page.screenshot(path="test-results/confirm_button_not_found.png")
                raise Exception("Кнопка подтверждения не найдена")

            print("✅ Кнопка подтверждения найдена")
            await confirm_button.click()

            # Ждем исчезновения диалога и обновления страницы
            await page.wait_for_load_state("networkidle")
            print("✅ Сообщество удалено")

            # Ждем исчезновения модального окна
            try:
                await page.wait_for_selector('[class*="backdrop"]', timeout=5000, state='hidden')
                print("✅ Модальное окно закрылось")
            except:
                print("⚠️ Модальное окно не закрылось автоматически")

            # Ждем обновления таблицы
            await page.wait_for_timeout(3000)  # Ждем 3 секунды для обновления

            # 6. Проверяем что сообщество действительно удалено
            print("🔍 Проверяем что сообщество удалено...")

            # Ждем немного для обновления списка
            await asyncio.sleep(2)

            # Проверяем что конкретное сообщество больше не отображается в таблице
            community_still_exists = await page.query_selector(f'table tbody tr:has-text("{test_community_slug}")')

            if community_still_exists:
                # Попробуем обновить страницу и проверить еще раз
                print("🔄 Обновляем страницу и проверяем еще раз...")
                await page.reload()
                await page.wait_for_load_state("networkidle")
                await page.wait_for_selector('table tbody tr', timeout=10000)

                # Проверяем еще раз после обновления
                community_still_exists = await page.query_selector(f'table tbody tr:has-text("{test_community_slug}")')

                if community_still_exists:
                    # Делаем скриншот для отладки
                    await page.screenshot(path="test-results/community_still_exists.png")

                    # Получаем список всех сообществ для отладки
                    all_communities = await page.evaluate("""
                        () => {
                            const rows = document.querySelectorAll('table tbody tr');
                            return Array.from(rows).map(row => {
                                const cells = row.querySelectorAll('td');
                                return {
                                    id: cells[0]?.textContent?.trim(),
                                    name: cells[1]?.textContent?.trim(),
                                    slug: cells[2]?.textContent?.trim()
                                };
                            });
                        }
                    """)

                    print(f"📋 Сообщества в таблице после обновления: {all_communities}")
                    raise Exception(f"Сообщество {test_community_name} (slug: {test_community_slug}) все еще отображается после удаления и обновления страницы")
                else:
                    print("✅ Сообщество удалено после обновления страницы")

            print("✅ Сообщество действительно удалено из списка")

            # 7. Делаем скриншот результата
            await page.screenshot(path="test-results/community_deleted_success.png")
            print("📸 Скриншот сохранен: test-results/community_deleted_success.png")

            print("🎉 E2E тест удаления сообщества прошел успешно!")

        except Exception as e:
            print(f"❌ Ошибка в E2E тесте: {e}")

            # Делаем скриншот при ошибке
            try:
                await page.screenshot(path=f"test-results/error_{int(time.time())}.png")
                print("📸 Скриншот ошибки сохранен")
            except Exception as screenshot_error:
                print(f"⚠️ Не удалось сделать скриншот при ошибке: {screenshot_error}")

            raise

    async def test_community_delete_without_permissions_browser(self, browser_setup, test_community_for_browser, frontend_url):
        """Тест попытки удаления без прав через браузер"""

        page = browser_setup["page"]

        try:
            # 1. Открываем админ-панель
            print("🔄 Открываем админ-панель...")
            await page.goto(f"{frontend_url}/admin")
            await page.wait_for_load_state("networkidle")

            # 2. Авторизуемся как обычный пользователь (без прав admin)
            print("🔐 Авторизуемся как обычный пользователь...")
            import os
            regular_username = os.getenv("TEST_REGULAR_USERNAME", "user2@example.com")
            password = os.getenv("E2E_TEST_PASSWORD", "password123")

            await page.fill("input[type='email']", regular_username)
            await page.fill("input[type='password']", password)
            await page.click("button[type='submit']")
            await page.wait_for_load_state("networkidle")

            # 3. Переходим на страницу сообществ
            print("🏘️ Переходим на страницу сообществ...")
            await page.click("a[href='/admin/communities']")
            await page.wait_for_load_state("networkidle")

            # 4. Ищем сообщество
            print(f"🔍 Ищем сообщество: {test_community_for_browser.name}")
            community_row = await page.wait_for_selector(
                f"tr:has-text('{test_community_for_browser.name}')",
                timeout=10000
            )

            if not community_row:
                print("❌ Сообщество не найдено")
                await page.screenshot(path="test-results/community_not_found_no_permissions.png")
                raise Exception("Сообщество не найдено")

            # 5. Проверяем что кнопка удаления недоступна или отсутствует
            print("🔒 Проверяем доступность кнопки удаления...")
            delete_button = await community_row.query_selector("button:has-text('Удалить')")

            if delete_button:
                # Если кнопка есть, пробуем нажать и проверяем ошибку
                print("⚠️ Кнопка удаления найдена, пробуем нажать...")
                await delete_button.click()

                # Ждем появления ошибки
                await page.wait_for_selector("[role='alert']", timeout=5000)
                error_message = await page.text_content("[role='alert']")

                if "Недостаточно прав" in error_message or "permission" in error_message.lower():
                    print("✅ Ошибка доступа получена корректно")
                else:
                    print(f"❌ Неожиданная ошибка: {error_message}")
                    await page.screenshot(path="test-results/unexpected_error.png")
                    raise Exception(f"Неожиданная ошибка: {error_message}")
            else:
                print("✅ Кнопка удаления недоступна (как и должно быть)")

            # 6. Проверяем что сообщество осталось в БД
            print("🗄️ Проверяем что сообщество осталось в БД...")
            with local_session() as session:
                community = session.query(Community).filter_by(
                    slug=test_community_for_browser.slug
                ).first()

                if not community:
                    print("❌ Сообщество было удалено без прав")
                    raise Exception("Сообщество было удалено без соответствующих прав")

                print("✅ Сообщество осталось в БД (как и должно быть)")

            print("🎉 E2E тест проверки прав доступа прошел успешно!")

        except Exception as e:
            try:
                await page.screenshot(path=f"test-results/error_permissions_{int(time.time())}.png")
            except:
                print("⚠️ Не удалось сделать скриншот при ошибке")
            print(f"❌ Ошибка в E2E тесте прав доступа: {e}")
            raise

    async def test_community_delete_ui_validation(self, browser_setup, test_community_for_browser, admin_user_for_browser, frontend_url):
        """Тест UI валидации при удалении сообщества"""

        page = browser_setup["page"]

        try:
            # 1. Авторизуемся как админ
            print("🔐 Авторизуемся как админ...")
            await page.goto(f"{frontend_url}/admin")
            await page.wait_for_load_state("networkidle")

            import os
            username = os.getenv("E2E_TEST_USERNAME", "test_admin@discours.io")
            password = os.getenv("E2E_TEST_PASSWORD", "password123")

            await page.fill("input[type='email']", username)
            await page.fill("input[type='password']", password)
            await page.click("button[type='submit']")
            await page.wait_for_load_state("networkidle")

            # 2. Переходим на страницу сообществ
            print("🏘️ Переходим на страницу сообществ...")
            await page.click("a[href='/admin/communities']")
            await page.wait_for_load_state("networkidle")

            # 3. Ищем сообщество и нажимаем удаление
            print(f"🔍 Ищем сообщество: {test_community_for_browser.name}")
            community_row = await page.wait_for_selector(
                f"tr:has-text('{test_community_for_browser.name}')",
                timeout=10000
            )

            delete_button = await community_row.query_selector("button:has-text('Удалить')")
            await delete_button.click()

            # 4. Проверяем модальное окно
            print("⚠️ Проверяем модальное окно...")
            modal = await page.wait_for_selector("[role='dialog']", timeout=10000)

            # Проверяем текст предупреждения
            modal_text = await modal.text_content()
            if "удалить" not in modal_text.lower() and "delete" not in modal_text.lower():
                print(f"❌ Неожиданный текст в модальном окне: {modal_text}")
                await page.screenshot(path="test-results/unexpected_modal_text.png")
                raise Exception("Неожиданный текст в модальном окне")

            # 5. Отменяем удаление
            print("❌ Отменяем удаление...")
            cancel_button = await page.query_selector("button:has-text('Отмена')")
            if not cancel_button:
                cancel_button = await page.query_selector("button:has-text('Cancel')")

            if cancel_button:
                await cancel_button.click()

                # Проверяем что модальное окно закрылось
                await page.wait_for_selector("[role='dialog']", state="hidden", timeout=5000)

                # Проверяем что сообщество осталось в таблице
                community_still_exists = await page.query_selector(
                    f"tr:has-text('{test_community_for_browser.name}')"
                )

                if not community_still_exists:
                    print("❌ Сообщество исчезло после отмены")
                    await page.screenshot(path="community_disappeared_after_cancel.png")
                    raise Exception("Сообщество исчезло после отмены удаления")

                print("✅ Сообщество осталось после отмены")
            else:
                print("⚠️ Кнопка отмены не найдена")

            print("🎉 E2E тест UI валидации прошел успешно!")

        except Exception as e:
            try:
                await page.screenshot(path=f"test-results/error_ui_validation_{int(time.time())}.png")
            except:
                print("⚠️ Не удалось сделать скриншот при ошибке")
            print(f"❌ Ошибка в E2E тесте UI валидации: {e}")
            raise
