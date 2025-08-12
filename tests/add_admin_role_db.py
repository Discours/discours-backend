#!/usr/bin/env python3
"""
Добавление роли админа пользователю test_admin@discours.io через базу данных
"""

import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine, text

from settings import DATABASE_URL


def add_admin_role_db():
    """Добавляем роль админа пользователю test_admin@discours.io через базу данных"""

    print("🔧 Подключаемся к базе данных...")
    engine = create_engine(DATABASE_URL)

    with engine.connect() as conn:
        # 1. Проверяем, что пользователь test_admin@discours.io существует
        print("🔍 Проверяем пользователя test_admin@discours.io...")
        result = conn.execute(text("SELECT id, name, email FROM author WHERE email = 'test_admin@discours.io'"))
        user = result.fetchone()

        if not user:
            print("❌ Пользователь test_admin@discours.io не найден в базе данных")
            return

        user_id = user[0]
        print(f"✅ Найден пользователь: {user[1]} (ID: {user_id}, email: {user[2]})")

        # 2. Проверяем, что системное сообщество существует
        print("🔍 Проверяем системное сообщество...")
        result = conn.execute(text("SELECT id, name, slug FROM community WHERE id = 1"))
        community = result.fetchone()

        if not community:
            print("❌ Системное сообщество (ID=1) не найдено в базе данных")
            return

        print(f"✅ Найдено системное сообщество: {community[1]} (ID: {community[0]}, slug: {community[2]})")

        # 3. Проверяем, есть ли уже роль у пользователя в системном сообществе
        print("🔍 Проверяем существующие роли...")
        result = conn.execute(
            text("""
            SELECT roles FROM community_author
            WHERE author_id = :user_id AND community_id = :community_id
        """),
            {"user_id": user_id, "community_id": 1},
        )

        existing_roles_row = result.fetchone()
        existing_roles = existing_roles_row[0].split(",") if existing_roles_row and existing_roles_row[0] else []
        print(f"📋 Существующие роли: {existing_roles}")

        # 4. Добавляем роль admin, если её нет
        if "admin" not in existing_roles:
            print("👑 Добавляем роль admin...")
            if existing_roles_row:
                # Обновляем существующую запись
                new_roles = ",".join(existing_roles + ["admin"])
                conn.execute(
                    text("""
                    UPDATE community_author
                    SET roles = :roles
                    WHERE author_id = :user_id AND community_id = :community_id
                """),
                    {"roles": new_roles, "user_id": user_id, "community_id": 1},
                )
            else:
                # Создаем новую запись
                conn.execute(
                    text("""
                    INSERT INTO community_author (community_id, author_id, roles, joined_at)
                    VALUES (:community_id, :user_id, :roles, :joined_at)
                """),
                    {"community_id": 1, "user_id": user_id, "roles": "admin", "joined_at": 0},
                )

            conn.commit()
            print("✅ Роль admin успешно добавлена")
        else:
            print("ℹ️ Роль admin уже существует")

        # 5. Проверяем результат
        print("🔍 Проверяем результат...")
        result = conn.execute(
            text("""
            SELECT roles FROM community_author
            WHERE author_id = :user_id AND community_id = :community_id
        """),
            {"user_id": user_id, "community_id": 1},
        )

        final_roles_row = result.fetchone()
        final_roles = final_roles_row[0].split(",") if final_roles_row and final_roles_row[0] else []
        print(f"📋 Финальные роли: {final_roles}")

        if "admin" in final_roles:
            print("🎉 Пользователь test_admin@discours.io теперь имеет роль admin в системном сообществе!")
        else:
            print("❌ Роль admin не была добавлена")


if __name__ == "__main__":
    add_admin_role_db()
