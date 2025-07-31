#!/usr/bin/env python3
"""
Добавление роли админа пользователю test_admin@discours.io
"""

import json

import requests


def add_admin_role():
    """Добавляем роль админа пользователю test_admin@discours.io"""

    # 1. Авторизуемся как системный админ (welcome@discours.io)
    print("🔐 Авторизуемся как системный админ...")
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
            "variables": {"email": "welcome@discours.io", "password": "password123"},
        },
    )

    login_data = login_response.json()
    print(f"📡 Ответ авторизации: {json.dumps(login_data, indent=2, ensure_ascii=False)}")

    if not login_data.get("data", {}).get("login", {}).get("success"):
        print("❌ Ошибка авторизации системного админа")
        return

    token = login_data["data"]["login"]["token"]
    admin_id = login_data["data"]["login"]["author"]["id"]
    print(f"✅ Авторизация успешна, системный админ ID: {admin_id}")

    # 2. Добавляем роль админа пользователю test_admin@discours.io в системном сообществе
    print("🔧 Добавляем роль админа пользователю test_admin@discours.io...")
    add_role_response = requests.post(
        "http://localhost:8000/graphql",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={
            "query": """
            mutation AddUserRole($community_id: Int!, $user_id: Int!, $role: String!) {
              add_user_role(community_id: $community_id, user_id: $user_id, role: $role) {
                success
                message
                error
              }
            }
            """,
            "variables": {
                "community_id": 1,  # Системное сообщество
                "user_id": 2500,  # test_admin@discours.io
                "role": "admin",
            },
        },
    )

    add_role_data = add_role_response.json()
    print(f"📡 Ответ добавления роли: {json.dumps(add_role_data, indent=2, ensure_ascii=False)}")

    if add_role_data.get("data", {}).get("add_user_role", {}).get("success"):
        print("✅ Роль админа успешно добавлена")

        # 3. Проверяем, что роль добавилась
        print("🔍 Проверяем роли пользователя...")
        check_roles_response = requests.post(
            "http://localhost:8000/graphql",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={
                "query": """
                query GetUserCommunityRoles($community_id: Int!, $user_id: Int!) {
                  adminGetUserCommunityRoles(community_id: $community_id, user_id: $user_id) {
                    roles
                    user {
                      id
                      name
                      email
                    }
                  }
                }
                """,
                "variables": {"community_id": 1, "user_id": 2500},
            },
        )

        check_roles_data = check_roles_response.json()
        print(f"📡 Ответ проверки ролей: {json.dumps(check_roles_data, indent=2, ensure_ascii=False)}")
    else:
        print("❌ Ошибка добавления роли")


if __name__ == "__main__":
    add_admin_role()
