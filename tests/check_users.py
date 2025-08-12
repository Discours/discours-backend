#!/usr/bin/env python3
"""
Проверка пользователей в системе
"""

import json

import requests


def check_users():
    """Проверяем пользователей в системе"""

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

    # 2. Получаем список пользователей
    print("🔍 Получаем список пользователей...")
    users_response = requests.post(
        "http://localhost:8000/graphql",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={
            "query": """
            query GetUsers {
              adminGetUsers {
                authors {
                  id
                  name
                  email
                  slug
                }
                total
                page
                perPage
                totalPages
              }
            }
            """
        },
    )

    users_data = users_response.json()
    print(f"📡 Ответ пользователей: {json.dumps(users_data, indent=2, ensure_ascii=False)}")

    # 3. Ищем системных админов
    if users_data.get("data", {}).get("adminGetUsers", {}).get("authors"):
        users = users_data["data"]["adminGetUsers"]["authors"]
        total = users_data["data"]["adminGetUsers"]["total"]
        print(f"\n📋 Найдено {len(users)} пользователей (всего: {total}):")

        system_admins = []
        for user in users:
            print(f"  - {user['name']} (ID: {user['id']}, email: {user.get('email', 'N/A')})")

            # Проверяем, является ли пользователь системным админом
            if user.get("email") in ["welcome@discours.io", "services@discours.io", "guests@discours.io"]:
                system_admins.append(user)
                print("    ✅ Системный админ")
            print()

        if system_admins:
            print(f"🎯 Найдено {len(system_admins)} системных админов:")
            for admin in system_admins:
                print(f"  - {admin['name']} (ID: {admin['id']}, email: {admin.get('email', 'N/A')})")
        else:
            print("❌ Системные админы не найдены")


if __name__ == "__main__":
    check_users()
