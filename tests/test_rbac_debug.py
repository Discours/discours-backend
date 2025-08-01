#!/usr/bin/env python3
"""
Тест для проверки RBAC модуля
"""

import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))


def test_rbac_import():
    """Тестируем импорт RBAC модуля"""
    try:
        from services.rbac import require_any_permission, require_permission

        print("✅ RBAC модуль импортирован успешно")

        # Проверяем, что функции существуют
        print(f"✅ require_permission: {require_permission}")
        print(f"✅ require_any_permission: {require_any_permission}")

        return True
    except Exception as e:
        print(f"❌ Ошибка импорта RBAC: {e}")
        return False


def test_require_permission_decorator():
    """Тестируем декоратор require_permission"""
    try:
        from services.rbac import require_permission

        @require_permission("test:permission")
        async def test_func(*args, **kwargs):
            return "success"

        print("✅ Декоратор require_permission создан успешно")
        return True
    except Exception as e:
        print(f"❌ Ошибка создания декоратора require_permission: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("🧪 Тестируем RBAC модуль...")

    if test_rbac_import():
        test_require_permission_decorator()

    print("🏁 Тест завершен")
