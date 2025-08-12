#!/usr/bin/env python3
"""
Проверка существующих сообществ
"""

import json

import requests


def check_communities():
    """Проверяем существующие сообщества"""

    # 1. Авторизуемся как test_admin@discours.io
    print("🔐 Авторизуемся как test_admin@discours.io...")
    login_response = requests.post(
        "http://localhost:8000/graphql",
        headers={"Content-Type": "application/json"},
        json={
            "query": """
            mutation Login($email: String!, $password: String!) {
              login(email: $email, password: $password) {
                success
                token
                author {
                  id
                  name
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
        print("❌ Ошибка авторизации test_admin@discours.io")
        return

    token = login_data["data"]["login"]["token"]
    user_id = login_data["data"]["login"]["author"]["id"]
    print(f"✅ Авторизация успешна, пользователь ID: {user_id}")

    # 2. Получаем все сообщества
    print("🔍 Получаем все сообщества...")
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
    print(f"📡 Ответ сообществ: {json.dumps(communities_data, indent=2, ensure_ascii=False)}")

    # 3. Ищем сообщества, созданные test_admin@discours.io
    if communities_data.get("data", {}).get("get_communities_all"):
        communities = communities_data["data"]["get_communities_all"]
        print(f"\n📋 Найдено {len(communities)} сообществ:")

        test_admin_communities = []
        for community in communities:
            creator = community.get("created_by", {})
            print(f"  - {community['name']} (ID: {community['id']}, slug: {community['slug']})")
            print(f"    Создатель: {creator.get('name', 'N/A')} (ID: {creator.get('id', 'N/A')})")

            if creator.get("id") == user_id:
                test_admin_communities.append(community)
                print("    ✅ Это сообщество создано test_admin@discours.io")
            print()

        if test_admin_communities:
            print(f"🎯 Найдено {len(test_admin_communities)} сообществ, созданных test_admin@discours.io:")
            for community in test_admin_communities:
                print(f"  - {community['name']} (ID: {community['id']}, slug: {community['slug']})")
        else:
            print("❌ test_admin@discours.io не создал ни одного сообщества")

    # 4. Проверяем права на удаление сообществ
    print("\n🔍 Проверяем права на удаление...")
    if communities_data.get("data", {}).get("get_communities_all"):
        communities = communities_data["data"]["get_communities_all"]
        if communities:
            test_community = communities[0]  # Берем первое сообщество для теста
            print(f"🧪 Тестируем удаление сообщества: {test_community['name']} (slug: {test_community['slug']})")

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
                    "variables": {"slug": test_community["slug"]},
                },
            )

            delete_data = delete_response.json()
            print(f"📡 Ответ удаления: {json.dumps(delete_data, indent=2, ensure_ascii=False)}")


if __name__ == "__main__":
    check_communities()
