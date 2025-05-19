import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from starlette.responses import JSONResponse, RedirectResponse

from auth.oauth import get_user_profile, oauth_login, oauth_callback

# Подменяем настройки для тестов
with (
    patch("auth.oauth.FRONTEND_URL", "http://localhost:3000"),
    patch(
        "auth.oauth.OAUTH_CLIENTS",
        {
            "GOOGLE": {"id": "test_google_id", "key": "test_google_secret"},
            "GITHUB": {"id": "test_github_id", "key": "test_github_secret"},
            "FACEBOOK": {"id": "test_facebook_id", "key": "test_facebook_secret"},
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
            response = await oauth_login(mock_request)

            assert isinstance(response, RedirectResponse)
            assert mock_request.session["provider"] == "google"
            assert "code_verifier" in mock_request.session
            assert "state" in mock_request.session

            mock_oauth_client.authorize_redirect.assert_called_once()

    @pytest.mark.asyncio
    async def test_oauth_login_invalid_provider(mock_request):
        """Тест с неправильным провайдером"""
        mock_request.path_params["provider"] = "invalid"

        response = await oauth_login(mock_request)

        assert isinstance(response, JSONResponse)
        assert response.status_code == 400
        assert "Invalid provider" in response.body.decode()

    @pytest.mark.asyncio
    async def test_oauth_callback_success(mock_request, mock_oauth_client):
        """Тест успешного OAuth callback"""
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
            patch("auth.oauth.local_session") as mock_session,
            patch("auth.oauth.TokenStorage.create_session", return_value="test_token"),
        ):
            # Мокаем сессию базы данных
            session = MagicMock()
            session.query.return_value.filter.return_value.first.return_value = None
            mock_session.return_value.__enter__.return_value = session

            response = await oauth_callback(mock_request)

            assert isinstance(response, RedirectResponse)
            assert response.status_code == 307
            assert "auth/success" in response.headers.get("location", "")

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

        response = await oauth_callback(mock_request)

        assert isinstance(response, JSONResponse)
        assert response.status_code == 400
        assert "Invalid state" in response.body.decode()

    @pytest.mark.asyncio
    async def test_oauth_callback_existing_user(mock_request, mock_oauth_client):
        """Тест OAuth callback с существующим пользователем"""
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
            patch("auth.oauth.local_session") as mock_session,
            patch("auth.oauth.TokenStorage.create_session", return_value="test_token"),
        ):
            # Мокаем существующего пользователя
            existing_user = MagicMock()
            session = MagicMock()
            session.query.return_value.filter.return_value.first.return_value = (
                existing_user
            )
            mock_session.return_value.__enter__.return_value = session

            response = await oauth_callback(mock_request)

            assert isinstance(response, RedirectResponse)
            assert response.status_code == 307

            # Проверяем обновление существующего пользователя
            assert existing_user.name == "Test User"
            assert existing_user.oauth == "google:123"
            assert existing_user.email_verified is True
