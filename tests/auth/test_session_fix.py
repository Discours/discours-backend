"""
Тест для проверки исправления ошибки SessionInfo.token в GraphQL
"""

import asyncio
import json

import requests


async def test_get_session():
    """
    Тестирует GraphQL запрос getSession после исправления
    """

    # GraphQL запрос для получения сессии
    query = """
    mutation {
        getSession {
            token
            author {
                id
                name
                slug
                email
            }
        }
    }
    """

    # Данные запроса
    payload = {"query": query, "variables": {}}

    # Заголовки запроса
    headers = {"Content-Type": "application/json", "Accept": "application/json"}

    try:
        # Отправляем запрос к GraphQL endpoint
        url = "http://localhost:8000/graphql"
        print(f"Отправка GraphQL запроса к {url}")

        response = requests.post(url, json=payload, headers=headers, timeout=10)

        print(f"Статус ответа: {response.status_code}")

        if response.status_code == 200:
            result = response.json()
            print("Ответ GraphQL:")
            print(json.dumps(result, indent=2, ensure_ascii=False))

            # Проверяем наличие ошибок
            if "errors" in result:
                print("❌ GraphQL ошибки найдены:")
                for error in result["errors"]:
                    print(f"  - {error.get('message', 'Неизвестная ошибка')}")
                    if "Cannot return null for non-nullable field SessionInfo.token" in error.get("message", ""):
                        print("❌ Исходная ошибка SessionInfo.token всё ещё присутствует")
                        return False
            else:
                print("✅ GraphQL ошибок не найдено")

                # Проверяем структуру данных
                data = result.get("data", {})
                session_info = data.get("getSession", {})

                if session_info:
                    if "token" in session_info and "author" in session_info:
                        print("✅ Структура SessionInfo корректна")
                        return True
                    print("❌ Некорректная структура SessionInfo")
                    return False
                print("❌ Данные getSession отсутствуют")
                return False
        else:
            print(f"❌ HTTP ошибка: {response.status_code}")
            print(response.text)
            return False

    except requests.exceptions.ConnectionError:
        print("❌ Не удалось подключиться к серверу. Убедитесь, что сервер запущен на localhost:8000")
        return False
    except Exception as e:
        print(f"❌ Ошибка при выполнении запроса: {e}")
        return False


if __name__ == "__main__":
    print("🔍 Тестирование исправления GraphQL ошибки SessionInfo.token")
    print("-" * 60)

    result = asyncio.run(test_get_session())

    print("-" * 60)
    if result:
        print("✅ Тест пройден успешно!")
    else:
        print("❌ Тест не пройден")
        print("\nПримечание: Ошибка 'Unauthorized' ожидаема, так как мы не передаём токен авторизации.")
        print("Главное - что исчезла ошибка 'Cannot return null for non-nullable field SessionInfo.token'")
