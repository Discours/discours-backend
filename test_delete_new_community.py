#!/usr/bin/env python3
"""
Тестирование удаления нового сообщества через API
"""

import json

import requests


def test_delete_new_community():
    """Тестируем удаление нового сообщества через API"""

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

    # 2. Проверяем, что сообщество существует
    print("🔍 Проверяем существование сообщества...")
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
    target_community = None
    for community in communities_data.get("data", {}).get("get_communities_all", []):
        if community["slug"] == "test-admin-community-e2e-1754005730":
            target_community = community
            break

    if not target_community:
        print("❌ Сообщество test-admin-community-e2e-1754005730 не найдено")
        return

    print(f"✅ Найдено сообщество: {target_community['name']} (ID: {target_community['id']})")
    print(f"   Создатель: {target_community['created_by']['name']} (ID: {target_community['created_by']['id']})")

    # 3. Пытаемся удалить сообщество
    print("🗑️ Пытаемся удалить сообщество...")
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
            "variables": {"slug": "test-admin-community-e2e-1754005730"},
        },
    )

    delete_data = delete_response.json()
    print(f"📡 Ответ удаления: {json.dumps(delete_data, indent=2, ensure_ascii=False)}")

    if delete_data.get("data", {}).get("delete_community", {}).get("success"):
        print("✅ Удаление прошло успешно")

        # 4. Проверяем, что сообщество действительно удалено
        print("🔍 Проверяем, что сообщество удалено...")
        check_response = requests.post(
            "http://localhost:8000/graphql",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={
                "query": """
                query GetCommunities {
                  get_communities_all {
                    id
                    name
                    slug
                  }
                }
                """
            },
        )

        check_data = check_response.json()
        still_exists = False
        for community in check_data.get("data", {}).get("get_communities_all", []):
            if community["slug"] == "test-admin-community-e2e-1754005730":
                still_exists = True
                break

        if still_exists:
            print("❌ Сообщество все еще существует после удаления")
        else:
            print("✅ Сообщество успешно удалено из базы данных")
    else:
        print("❌ Ошибка удаления")
        error = delete_data.get("data", {}).get("delete_community", {}).get("error")
        print(f"Ошибка: {error}")


if __name__ == "__main__":
    test_delete_new_community()
