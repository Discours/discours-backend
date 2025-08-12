import pytest

PORT = 8000

@pytest.fixture
def oauth_settings() -> dict[str, dict[str, str]]:
    """Тестовые настройки OAuth"""
    return {
        "GOOGLE": {"id": "test_google_id", "key": "test_google_secret"},
        "GITHUB": {"id": "test_github_id", "key": "test_github_secret"},
        "FACEBOOK": {"id": "test_facebook_id", "key": "test_facebook_secret"},
    }


@pytest.fixture
def frontend_url() -> str:
    """URL фронтенда для тестов"""
    return f"https://localhost:{PORT}"


@pytest.fixture(autouse=True)
def mock_settings(monkeypatch, oauth_settings, frontend_url):
    """Подменяем настройки для тестов"""
    monkeypatch.setattr("auth.oauth.OAUTH_CLIENTS", oauth_settings)
    monkeypatch.setattr("auth.oauth.FRONTEND_URL", frontend_url)
