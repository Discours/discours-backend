import json
import time

import requests


def test_e2e_community_delete_workflow():
    """Упрощенный E2E тест удаления сообщества без браузера"""

    url = "http://localhost:8000/graphql"
    headers = {"Content-Type": "application/json"}

    print("🔐 E2E тест удаления сообщества...\n")

    # 1. Авторизация
    print("1️⃣ Авторизуемся...")
    login_query = """
    mutation Login($email: String!, $password: String!) {
      login(email: $email, password: $password) {
        success
        token
        author {
          id
          email
        }
        error
      }
    }
    """

    variables = {"email": "test_admin@discours.io", "password": "password123"}

    data = {"query": login_query, "variables": variables}

    response = requests.post(url, headers=headers, json=data)
    result = response.json()

    if not result.get("data", {}).get("login", {}).get("success"):
        print(f"❌ Авторизация не удалась: {result}")
        return False

    token = result["data"]["login"]["token"]
    print(f"✅ Авторизация успешна, токен: {token[:50]}...")

    # 2. Получаем список сообществ
    print("\n2️⃣ Получаем список сообществ...")
    headers_with_auth = {"Content-Type": "application/json", "Authorization": f"Bearer {token}"}

    communities_query = """
    query {
      get_communities_all {
        id
        name
        slug
      }
    }
    """

    data = {"query": communities_query}
    response = requests.post(url, headers=headers_with_auth, json=data)
    result = response.json()

    communities = result.get("data", {}).get("get_communities_all", [])
    test_community = None

    for community in communities:
        if community["name"] == "Test Community":
            test_community = community
            break

    if not test_community:
        print("❌ Сообщество Test Community не найдено")
        return False

    print(
        f"✅ Найдено сообщество: {test_community['name']} (ID: {test_community['id']}, slug: {test_community['slug']})"
    )

    # 3. Удаляем сообщество
    print("\n3️⃣ Удаляем сообщество...")
    delete_query = """
    mutation DeleteCommunity($slug: String!) {
      delete_community(slug: $slug) {
        success
        message
        error
      }
    }
    """

    variables = {"slug": test_community["slug"]}
    data = {"query": delete_query, "variables": variables}

    response = requests.post(url, headers=headers_with_auth, json=data)
    result = response.json()

    print("Ответ сервера:")
    print(json.dumps(result, indent=2, ensure_ascii=False))

    if not result.get("data", {}).get("delete_community", {}).get("success"):
        print("❌ Ошибка удаления сообщества")
        return False

    print("✅ Сообщество успешно удалено!")

    # 4. Проверяем что сообщество удалено
    print("\n4️⃣ Проверяем что сообщество удалено...")
    time.sleep(1)  # Даем время на обновление БД

    data = {"query": communities_query}
    response = requests.post(url, headers=headers_with_auth, json=data)
    result = response.json()

    communities_after = result.get("data", {}).get("get_communities_all", [])
    community_still_exists = any(c["slug"] == test_community["slug"] for c in communities_after)

    if community_still_exists:
        print("❌ Сообщество все еще в списке")
        return False

    print("✅ Сообщество действительно удалено из списка")

    print("\n🎉 E2E тест удаления сообщества прошел успешно!")
    return True


if __name__ == "__main__":
    success = test_e2e_community_delete_workflow()
    if not success:
        exit(1)
