from unittest.mock import AsyncMock, MagicMock, patch

import time
import pytest
from starlette.responses import JSONResponse, RedirectResponse

from auth.oauth import get_user_profile, oauth_callback_http, oauth_login_http
from auth.orm import Author
from services.db import local_session

# Подменяем настройки для тестов
with (
    patch("auth.oauth.FRONTEND_URL", "https://localhost:3000"),
    patch(
        "auth.oauth.OAUTH_CLIENTS",
        {
            "GOOGLE": {"id": "test_google_id", "key": "test_google_secret"},
            "GITHUB": {"id": "test_github_id", "key": "test_github_secret"},
            "FACEBOOK": {"id": "test_facebook_id", "key": "test_facebook_secret"},
            "YANDEX": {"id": "test_yandex_id", "key": "test_yandex_secret"},
            "TWITTER": {"id": "test_twitter_id", "key": "test_twitter_secret"},
            "TELEGRAM": {"id": "test_telegram_id", "key": "test_telegram_secret"},
            "VK": {"id": "test_vk_id", "key": "test_vk_secret"},
        },
    ),
):

    @pytest.fixture
    def mock_request():
        """Фикстура для мока запроса"""
        request = MagicMock()
        request.session = {}
        request.path_params = {}
        request.query_params = {}
        return request

    @pytest.fixture
    def mock_oauth_client():
        """Фикстура для мока OAuth клиента"""
        client = AsyncMock()
        client.authorize_redirect = AsyncMock()
        client.authorize_access_token = AsyncMock()
        client.get = AsyncMock()
        return client

    @pytest.mark.asyncio
    async def test_get_user_profile_google():
        """Тест получения профиля из Google"""
        client = AsyncMock()
        token = {
            "userinfo": {
                "sub": "123",
                "email": "test@gmail.com",
                "name": "Test User",
                "picture": "https://lh3.googleusercontent.com/photo=s96",
            }
        }

        profile = await get_user_profile("google", client, token)

        assert profile["id"] == "123"
        assert profile["email"] == "test@gmail.com"
        assert profile["name"] == "Test User"
        assert profile["picture"] == "https://lh3.googleusercontent.com/photo=s600"

    @pytest.mark.asyncio
    async def test_get_user_profile_github():
        """Тест получения профиля из GitHub"""
        client = AsyncMock()
        client.get.side_effect = [
            MagicMock(
                json=lambda: {
                    "id": 456,
                    "login": "testuser",
                    "name": "Test User",
                    "avatar_url": "https://github.com/avatar.jpg",
                }
            ),
            MagicMock(
                json=lambda: [
                    {"email": "other@github.com", "primary": False},
                    {"email": "test@github.com", "primary": True},
                ]
            ),
        ]

        profile = await get_user_profile("github", client, {})

        assert profile["id"] == "456"
        assert profile["email"] == "test@github.com"
        assert profile["name"] == "Test User"
        assert profile["picture"] == "https://github.com/avatar.jpg"

    @pytest.mark.asyncio
    async def test_get_user_profile_facebook():
        """Тест получения профиля из Facebook"""
        client = AsyncMock()
        client.get.return_value = MagicMock(
            json=lambda: {
                "id": "789",
                "name": "Test User",
                "email": "test@facebook.com",
                "picture": {"data": {"url": "https://facebook.com/photo.jpg"}},
            }
        )

        profile = await get_user_profile("facebook", client, {})

        assert profile["id"] == "789"
        assert profile["email"] == "test@facebook.com"
        assert profile["name"] == "Test User"
        assert profile["picture"] == "https://facebook.com/photo.jpg"

    @pytest.mark.asyncio
    async def test_oauth_login_success(mock_request, mock_oauth_client):
        """Тест успешного начала OAuth авторизации"""
        mock_request.path_params["provider"] = "google"

        # Настраиваем мок для authorize_redirect
        redirect_response = RedirectResponse(url="http://example.com")
        mock_oauth_client.authorize_redirect.return_value = redirect_response

        with patch("auth.oauth.oauth.create_client", return_value=mock_oauth_client):
            response = await oauth_login_http(mock_request)

            assert isinstance(response, RedirectResponse)
            assert mock_request.session["provider"] == "google"
            assert "code_verifier" in mock_request.session
            assert "state" in mock_request.session

            mock_oauth_client.authorize_redirect.assert_called_once()

    @pytest.mark.asyncio
    async def test_oauth_login_invalid_provider(mock_request):
        """Тест с неправильным провайдером"""
        mock_request.path_params["provider"] = "invalid"

        response = await oauth_login_http(mock_request)

        assert isinstance(response, JSONResponse)
        assert response.status_code == 400
        body_content = response.body
        if isinstance(body_content, memoryview):
            body_content = bytes(body_content)
        assert "Invalid provider" in body_content.decode()

    @pytest.mark.asyncio
    async def test_oauth_callback_success(mock_request, mock_oauth_client, oauth_db_session):
        """Тест успешного OAuth callback с правильной БД"""
        mock_request.session = {
            "provider": "google",
            "code_verifier": "test_verifier",
            "state": "test_state",
        }
        mock_request.query_params["state"] = "test_state"

        mock_oauth_client.authorize_access_token.return_value = {
            "userinfo": {"sub": "123", "email": "test@gmail.com", "name": "Test User"}
        }

        with (
            patch("auth.oauth.oauth.create_client", return_value=mock_oauth_client),
            patch("auth.oauth.TokenStorage.create_session", return_value="test_token"),
            patch("auth.oauth.get_oauth_state", return_value={"provider": "google", "redirect_uri": "https://localhost:3000"}),
        ):
            response = await oauth_callback_http(mock_request)

            assert isinstance(response, RedirectResponse)
            assert response.status_code == 307
            assert "/auth/success" in response.headers.get("location", "")

            # Проверяем cookie
            cookies = response.headers.getlist("set-cookie")
            assert any("session_token=test_token" in cookie for cookie in cookies)
            assert any("httponly" in cookie.lower() for cookie in cookies)
            assert any("secure" in cookie.lower() for cookie in cookies)

            # Проверяем очистку сессии
            assert "code_verifier" not in mock_request.session
            assert "provider" not in mock_request.session
            assert "state" not in mock_request.session

    @pytest.mark.asyncio
    async def test_oauth_callback_invalid_state(mock_request):
        """Тест с неправильным state параметром"""
        mock_request.session = {"provider": "google", "state": "correct_state"}
        mock_request.query_params["state"] = "wrong_state"

        with patch("auth.oauth.get_oauth_state", return_value=None):
            response = await oauth_callback_http(mock_request)

            assert isinstance(response, JSONResponse)
            assert response.status_code == 400
            body_content = response.body
            if isinstance(body_content, memoryview):
                body_content = bytes(body_content)
            assert "Invalid or expired OAuth state" in body_content.decode()

    @pytest.mark.asyncio
    async def test_oauth_callback_existing_user(mock_request, mock_oauth_client, oauth_db_session):
        """Тест OAuth callback с существующим пользователем через реальную БД"""
        # Сессия уже предоставлена через oauth_db_session fixture
        session = oauth_db_session

        # Создаем тестового пользователя заранее
        existing_user = Author(
            email="test@gmail.com",
            name="Test User",
            slug="test-user",
            email_verified=False,
            created_at=int(time.time()),
            updated_at=int(time.time()),
            last_seen=int(time.time())
        )
        session.add(existing_user)
        session.commit()

        mock_request.session = {
            "provider": "google",
            "code_verifier": "test_verifier",
            "state": "test_state",
        }
        mock_request.query_params["state"] = "test_state"

        mock_oauth_client.authorize_access_token.return_value = {
            "userinfo": {"sub": "123", "email": "test@gmail.com", "name": "Test User"}
        }

        with (
            patch("auth.oauth.oauth.create_client", return_value=mock_oauth_client),
            patch("auth.oauth.TokenStorage.create_session", return_value="test_token"),
            patch("auth.oauth.get_oauth_state", return_value={"provider": "google", "redirect_uri": "https://localhost:3000"}),
        ):
            response = await oauth_callback_http(mock_request)

            assert isinstance(response, RedirectResponse)
            assert response.status_code == 307

            # Проверяем что пользователь был обновлен в БД через OAuth flow
            updated_user = session.query(Author).where(Author.email == "test@gmail.com").first()
            assert updated_user is not None
            # Проверяем что пользователь существует и имеет OAuth данные
            assert updated_user.email == "test@gmail.com"
            assert updated_user.name == "Test User"

# Импортируем необходимые модели
from orm.community import Community, CommunityAuthor

@pytest.fixture
def oauth_db_session():
    """Фикстура для сессии базы данных в OAuth тестах"""
    from services.db import local_session
    session = local_session()
    try:
        yield session
    finally:
        session.close()

@pytest.fixture
def simple_user(oauth_db_session):
    """Фикстура для простого пользователя"""
    from auth.orm import Author
    import time
    
    # Создаем тестового пользователя
    user = Author(
        email="simple@test.com",
        name="Simple User",
        slug="simple-user",
        email_verified=True,
        created_at=int(time.time()),
        updated_at=int(time.time()),
        last_seen=int(time.time())
    )
    oauth_db_session.add(user)
    oauth_db_session.commit()
    
    yield user
    
    # Очистка
    try:
        oauth_db_session.query(Author).where(Author.id == user.id).delete()
        oauth_db_session.commit()
    except Exception:
        oauth_db_session.rollback()

@pytest.fixture
def test_community(oauth_db_session, simple_user):
    """
    Создает тестовое сообщество с ожидаемыми ролями по умолчанию

    Args:
        oauth_db_session: Сессия базы данных для теста
        simple_user: Пользователь для создания сообщества

    Returns:
        Community: Созданное тестовое сообщество
    """
    # Очищаем существующие записи
    oauth_db_session.query(Community).where(
        (Community.id == 300) | (Community.slug == "test-oauth-community")
    ).delete()
    oauth_db_session.commit()

    # Создаем тестовое сообщество
    community = Community(
        id=300,
        name="Test OAuth Community",
        slug="test-oauth-community",
        desc="Community for OAuth tests",
        created_by=simple_user.id,
        settings={
            "default_roles": ["reader", "author"],
            "available_roles": ["reader", "author", "editor"]
        }
    )
    oauth_db_session.add(community)
    oauth_db_session.commit()

    yield community

    # Очистка после теста
    try:
        oauth_db_session.query(CommunityAuthor).where(
            CommunityAuthor.community_id == community.id
        ).delete()
        oauth_db_session.query(Community).where(Community.id == community.id).delete()
        oauth_db_session.commit()
    except Exception:
        oauth_db_session.rollback()
