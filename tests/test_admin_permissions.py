#!/usr/bin/env python3
"""
Временный тест для проверки прав роли admin
"""

import asyncio
import json
from pathlib import Path

async def test_admin_permissions():
    """Проверяем, что у роли admin есть все необходимые права"""

    # Загружаем дефолтные права
    with Path("services/default_role_permissions.json").open() as f:
        default_permissions = json.load(f)

    # Получаем права роли admin
    admin_permissions = default_permissions.get("admin", [])

    # Проверяем наличие критических прав
    critical_permissions = [
        "community:delete",
        "community:delete_any",
        "community:update",
        "community:update_any"
    ]

    print("Права роли admin:")
    for perm in admin_permissions:
        print(f"  - {perm}")

    print("\nПроверка критических прав:")
    for perm in critical_permissions:
        if perm in admin_permissions:
            print(f"  ✓ {perm}")
        else:
            print(f"  ✗ {perm} - ОТСУТСТВУЕТ!")

    # Проверяем наследование от editor
    editor_permissions = default_permissions.get("editor", [])
    print(f"\nПрава editor (наследуются admin):")
    for perm in editor_permissions:
        print(f"  - {perm}")

if __name__ == "__main__":
    asyncio.run(test_admin_permissions())
