#!/usr/bin/env python3
"""
Создание сообщества в базе данных напрямую для test_admin@discours.io
"""

import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import time

from sqlalchemy import create_engine, text

from settings import DATABASE_URL


def create_community_db():
    """Создаем сообщество в базе данных напрямую для test_admin@discours.io"""

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

        # 2. Создаем новое сообщество
        print("🏘️ Создаем новое сообщество...")
        community_name = "Test Admin Community E2E"
        community_slug = f"test-admin-community-e2e-{int(time.time())}"
        community_desc = "Сообщество для E2E тестирования удаления"

        # Вставляем сообщество
        result = conn.execute(
            text("""
            INSERT INTO community (name, slug, desc, pic, created_by, created_at)
            VALUES (:name, :slug, :desc, :pic, :created_by, :created_at)
        """),
            {
                "name": community_name,
                "slug": community_slug,
                "desc": community_desc,
                "pic": "",  # Пустое поле для изображения
                "created_by": user_id,
                "created_at": int(time.time()),
            },
        )

        # Получаем ID созданного сообщества
        community_id = conn.execute(text("SELECT last_insert_rowid()")).scalar()

        conn.commit()
        print(f"✅ Сообщество создано: {community_name} (ID: {community_id}, slug: {community_slug})")

        # 3. Добавляем создателя как админа сообщества
        print("👑 Добавляем создателя как админа сообщества...")
        conn.execute(
            text("""
            INSERT INTO community_author (community_id, author_id, roles, joined_at)
            VALUES (:community_id, :author_id, :roles, :joined_at)
        """),
            {
                "community_id": community_id,
                "author_id": user_id,
                "roles": "admin,author,editor",
                "joined_at": int(time.time()),
            },
        )

        conn.commit()
        print("✅ Создатель добавлен как админ сообщества")

        # 4. Проверяем результат
        print("🔍 Проверяем результат...")
        result = conn.execute(
            text("""
            SELECT c.id, c.name, c.slug, c.created_by, a.name as creator_name
            FROM community c
            JOIN author a ON c.created_by = a.id
            WHERE c.id = :community_id
        """),
            {"community_id": community_id},
        )

        community = result.fetchone()
        if community:
            print("✅ Сообщество в базе данных:")
            print(f"  - ID: {community[0]}")
            print(f"  - Название: {community[1]}")
            print(f"  - Slug: {community[2]}")
            print(f"  - Создатель ID: {community[3]}")
            print(f"  - Создатель: {community[4]}")

        # Проверяем роли
        result = conn.execute(
            text("""
            SELECT roles FROM community_author
            WHERE community_id = :community_id AND author_id = :author_id
        """),
            {"community_id": community_id, "author_id": user_id},
        )

        roles_row = result.fetchone()
        if roles_row:
            roles = roles_row[0].split(",") if roles_row[0] else []
            print(f"✅ Роли создателя в сообществе: {roles}")

        print("\n🎉 Сообщество успешно создано!")
        print("📋 Для использования в E2E тесте:")
        print(f"  - ID: {community_id}")
        print(f"  - Slug: {community_slug}")
        print(f"  - Название: {community_name}")


if __name__ == "__main__":
    create_community_db()
