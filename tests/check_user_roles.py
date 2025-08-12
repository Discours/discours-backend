#!/usr/bin/env python3
"""
Проверка ролей пользователя
"""

import json

import requests


def check_user_roles():
    """Проверяем роли пользователя test_admin@discours.io"""

    # 1. Авторизуемся
    print("🔐 Авторизуемся...")
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
    print(f"📡 Ответ авторизации: {json.dumps(login_data, indent=2, ensure_ascii=False)}")

    if not login_data.get("data", {}).get("login", {}).get("success"):
        print("❌ Ошибка авторизации")
        return

    token = login_data["data"]["login"]["token"]
    user_id = login_data["data"]["login"]["author"]["id"]
    print(f"✅ Авторизация успешна, пользователь ID: {user_id}")

    # 2. Проверяем, является ли пользователь админом
    print("🔍 Проверяем админские права...")
    admin_response = requests.post(
        "http://localhost:8000/graphql",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={
            "query": """
            query CheckAdmin {
              isAdmin
            }
            """
        },
    )

    admin_data = admin_response.json()
    print(f"📡 Ответ админ-проверки: {json.dumps(admin_data, indent=2, ensure_ascii=False)}")

    # 3. Проверяем роли пользователя
    print("🔍 Проверяем роли пользователя...")
    roles_response = requests.post(
        "http://localhost:8000/graphql",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={
            "query": """
            query GetRoles {
              getRoles {
                id
                name
              }
            }
            """
        },
    )

    roles_data = roles_response.json()
    print(f"📡 Ответ ролей: {json.dumps(roles_data, indent=2, ensure_ascii=False)}")

    # 4. Проверяем админские роли
    print("🔍 Проверяем админские роли...")
    admin_roles_response = requests.post(
        "http://localhost:8000/graphql",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={
            "query": """
            query GetAdminRoles {
              adminGetRoles {
                id
                name
              }
            }
            """
        },
    )

    admin_roles_data = admin_roles_response.json()
    print(f"📡 Ответ админ-ролей: {json.dumps(admin_roles_data, indent=2, ensure_ascii=False)}")


if __name__ == "__main__":
    check_user_roles()
