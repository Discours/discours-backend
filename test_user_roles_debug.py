#!/usr/bin/env python3
"""
Тест для проверки ролей пользователя
"""

import requests


def test_user_roles():
    # 1. Авторизуемся
    print("🔐 Авторизуемся...")
    login_response = requests.post(
        "http://localhost:8000/graphql",
        json={
            "query": """
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
            """,
            "variables": {"email": "test_admin@discours.io", "password": "password123"},
        },
    )

    login_data = login_response.json()
    if not login_data.get("data", {}).get("login", {}).get("success"):
        print("❌ Авторизация не удалась")
        return

    token = login_data["data"]["login"]["token"]
    user_id = login_data["data"]["login"]["author"]["id"]
    print(f"✅ Авторизация успешна, пользователь ID: {user_id}")

    # 2. Получаем все сообщества
    print("🏘️ Получаем все сообщества...")
    communities_response = requests.post(
        "http://localhost:8000/graphql",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={
            "query": """
            query GetCommunities {
              get_communities_all {
                id
                name
                slug
                created_by {
                  id
                  name
                  email
                }
              }
            }
            """
        },
    )

    communities_data = communities_response.json()
    communities = communities_data.get("data", {}).get("get_communities_all", [])

    # Ищем сообщества с именем "Test Community"
    test_communities = []
    for community in communities:
        if "Test Community" in community["name"]:
            test_communities.append(community)

    print("📋 Сообщества с именем 'Test Community':")
    for community in test_communities:
        print(f"  - ID: {community['id']}, Name: '{community['name']}', Slug: {community['slug']}")
        print(f"    Создатель: {community['created_by']}")

    if test_communities:
        # Берем первое сообщество для тестирования
        test_community = test_communities[0]
        print(f"✅ Будем тестировать удаление сообщества: {test_community['name']} (slug: {test_community['slug']})")

        # Сохраняем информацию для E2E теста
        print("📝 Для E2E теста используйте:")
        print(f'   test_community_name = "{test_community["name"]}"')
        print(f'   test_community_slug = "{test_community["slug"]}"')


if __name__ == "__main__":
    test_user_roles()
