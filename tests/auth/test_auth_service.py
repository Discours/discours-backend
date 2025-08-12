import pytest
from services.auth import AuthService
from services.db import local_session
from auth.orm import Author

@pytest.mark.asyncio
async def test_ensure_user_has_reader_role():
    """Тест добавления роли reader пользователю"""
    
    auth_service = AuthService()

    # Создаем тестового пользователя без роли reader
    with local_session() as session:
        test_author = Author(
            email="test_reader_role@example.com",
            slug="test_reader_role",
            password="test_password"
        )
        session.add(test_author)
        session.commit()
        user_id = test_author.id

    try:
        # Проверяем, что роль reader добавляется
        result = await auth_service.ensure_user_has_reader_role(user_id)
        assert result is True

        # Проверяем, что при повторном вызове возвращается True
        result = await auth_service.ensure_user_has_reader_role(user_id)
        assert result is True
    finally:
        # Очищаем тестовые данные
        with local_session() as session:
            test_author = session.query(Author).filter_by(id=user_id).first()
            if test_author:
                session.delete(test_author)
            session.commit()
