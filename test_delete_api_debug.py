#!/usr/bin/env python3
"""
Тест для отладки удаления сообщества через API
"""

import json

import requests


def test_delete_community_api():
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
    print(f"📡 Ответ авторизации: {json.dumps(login_data, indent=2)}")

    if not login_data.get("data", {}).get("login", {}).get("success"):
        print("❌ Авторизация не удалась")
        return

    token = login_data["data"]["login"]["token"]
    print(f"✅ Авторизация успешна, токен: {token[:20]}...")

    # 2. Удаляем сообщество
    print("🗑️ Удаляем сообщество...")
    delete_response = requests.post(
        "http://localhost:8000/graphql",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={
            "query": """
            mutation DeleteCommunity($slug: String!) {
              delete_community(slug: $slug) {
                success
                message
                error
              }
            }
            """,
            "variables": {"slug": "test-community-test-995f4965"},
        },
    )

    delete_data = delete_response.json()
    print(f"📡 Ответ удаления: {json.dumps(delete_data, indent=2)}")

    if delete_data.get("data", {}).get("delete_community", {}).get("success"):
        print("✅ Удаление прошло успешно")
    else:
        print("❌ Удаление не удалось")
        error = delete_data.get("data", {}).get("delete_community", {}).get("error")
        print(f"Ошибка: {error}")

    # 3. Проверяем что сообщество удалено
    print("🔍 Проверяем что сообщество удалено...")
    check_response = requests.post(
        "http://localhost:8000/graphql",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={
            "query": """
            query GetCommunities {
              get_communities_all {
                id
                slug
                name
              }
            }
            """
        },
    )

    check_data = check_response.json()
    communities = check_data.get("data", {}).get("get_communities_all", [])

    # Ищем наше сообщество
    target_community = None
    for community in communities:
        if community["slug"] == "test-community-test-995f4965":
            target_community = community
            break

    if target_community:
        print(f"❌ Сообщество все еще существует: {target_community}")
    else:
        print("✅ Сообщество успешно удалено")


if __name__ == "__main__":
    test_delete_community_api()
