#!/usr/bin/env python3
"""
Отладочный скрипт для проверки содержимого GraphQL контекста
"""

import json

import requests

# GraphQL endpoint
url = "http://localhost:8000/graphql"

# Сначала авторизуемся
login_mutation = """
mutation Login($email: String!, $password: String!) {
    login(email: $email, password: $password) {
        token
        author {
            id
            name
            email
        }
    }
}
"""

login_variables = {"email": "test_admin@discours.io", "password": "password123"}

print("🔐 Авторизуемся...")
response = requests.post(url, json={"query": login_mutation, "variables": login_variables})

if response.status_code != 200:
    print(f"❌ Ошибка авторизации: {response.status_code}")
    print(response.text)
    exit(1)

login_data = response.json()
print(f"✅ Авторизация успешна: {json.dumps(login_data, indent=2)}")

if "errors" in login_data:
    print(f"❌ Ошибки в авторизации: {login_data['errors']}")
    exit(1)

token = login_data["data"]["login"]["token"]
author_id = login_data["data"]["login"]["author"]["id"]
print(f"🔑 Токен получен: {token[:50]}...")
print(f"👤 Author ID: {author_id}")

# Теперь попробуем удалить сообщество
delete_mutation = """
mutation DeleteCommunity($slug: String!) {
    delete_community(slug: $slug) {
        success
        error
    }
}
"""

delete_variables = {"slug": "test-admin-community-e2e-1754005730"}

headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

print(f"\n🗑️ Пытаемся удалить сообщество {delete_variables['slug']}...")
response = requests.post(url, json={"query": delete_mutation, "variables": delete_variables}, headers=headers)

print(f"📊 Статус ответа: {response.status_code}")
print(f"📄 Ответ: {response.text}")

if response.status_code == 200:
    data = response.json()
    print(f"📋 JSON ответ: {json.dumps(data, indent=2)}")

    if "errors" in data:
        print(f"❌ GraphQL ошибки: {data['errors']}")
    else:
        print(f"✅ Результат: {data['data']['delete_community']}")
else:
    print(f"❌ HTTP ошибка: {response.status_code}")
