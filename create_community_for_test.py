#!/usr/bin/env python3
"""
Создание сообщества для test_admin@discours.io
"""

import json

import requests


def create_community():
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

    # 2. Создаем сообщество
    print("🏘️ Создаем сообщество...")
    create_response = requests.post(
        "http://localhost:8000/graphql",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={
            "query": """
            mutation CreateCommunity($community_input: CommunityInput!) {
              create_community(community_input: $community_input) {
                success
                community {
                  id
                  name
                  slug
                  desc
                  created_by {
                    id
                    name
                    email
                  }
                }
                error
              }
            }
            """,
            "variables": {
                "community_input": {
                    "name": "Test Admin Community",
                    "slug": "test-admin-community-e2e",
                    "desc": "Сообщество для E2E тестирования удаления",
                }
            },
        },
    )

    create_data = create_response.json()
    print(f"📡 Ответ создания: {json.dumps(create_data, indent=2)}")

    if create_data.get("data", {}).get("create_community", {}).get("success"):
        community = create_data["data"]["create_community"]["community"]
        print("✅ Сообщество создано успешно!")
        print(f"   ID: {community['id']}")
        print(f"   Name: {community['name']}")
        print(f"   Slug: {community['slug']}")
        print(f"   Создатель: {community['created_by']}")

        print("📝 Для E2E теста используйте:")
        print(f'   test_community_name = "{community["name"]}"')
        print(f'   test_community_slug = "{community["slug"]}"')
    else:
        print("❌ Создание сообщества не удалось")
        error = create_data.get("data", {}).get("create_community", {}).get("error")
        print(f"Ошибка: {error}")


if __name__ == "__main__":
    create_community()
