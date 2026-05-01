import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi.responses import RedirectResponse
from app.models import User
from sqlmodel import select

@pytest.mark.asyncio
async def test_auth_callback_redirects_to_dashboard(client, session, mocker):
    # Mock GoogleAuthService methods
    mock_token = {"access_token": "fake-token", "userinfo": {"sub": "12345", "email": "test@example.com", "name": "Test User"}}
    
    mocker.patch("app.api.v1.routes.google_auth.authorize_access_token", return_value=mock_token)
    mocker.patch("app.api.v1.routes.google_auth.get_user_info", return_value=mock_token["userinfo"])
    
    # Properly mock app.storage.user to avoid "UI context" error
    # We mock the entire storage object and then the user property
    mock_storage = MagicMock()
    mock_user = MagicMock()
    mock_storage.user = mock_user
    mocker.patch("app.api.v1.routes.app.storage", mock_storage)
    
    # Call the callback endpoint
    response = client.get("/api/v1/auth/callback", follow_redirects=False)
    
    # Verify redirection
    assert response.status_code == 307  # RedirectResponse default status code in Starlette
    assert response.headers["location"] == "/dashboard"
    
    # Verify user was created in the database
    statement = select(User).where(User.email == "test@example.com")
    user = session.exec(statement).first()
    assert user is not None
    assert user.sub == "12345"
    assert user.name == "Test User"
    
    # Verify cookie was set
    assert "paws_user_id" in response.cookies
    assert response.cookies["paws_user_id"] == str(user.id)
    
    # Verify NiceGUI storage was updated
    mock_user.update.assert_called_once()

@pytest.mark.asyncio
async def test_auth_login_redirects_to_google(client, mocker):
    # Mock authorize_redirect
    mock_redirect = RedirectResponse(url="https://accounts.google.com/o/oauth2/v2/auth?...")
    mocker.patch("app.api.v1.routes.google_auth.authorize_redirect", return_value=mock_redirect)
    
    response = client.get("/api/v1/auth/login", follow_redirects=False)
    
    assert response.status_code == 307
    assert response.headers["location"].startswith("https://accounts.google.com")

@pytest.mark.asyncio
async def test_auth_login_no_500_error(client, mocker):
    # This test verifies that SessionMiddleware is working and Authlib doesn't crash
    # when trying to access request.session
    
    # We mock the low-level oauth.google.authorize_redirect instead of google_auth.authorize_redirect
    mock_response = RedirectResponse(url="https://accounts.google.com/o/oauth2/v2/auth")
    mocker.patch("app.services.integrations.oauth.google.authorize_redirect", return_value=mock_response)
    
    # Mock client_id so it doesn't return early
    mocker.patch("app.api.v1.routes.google_auth.client_id", "fake-client-id")
    
    response = client.get("/api/v1/auth/login", follow_redirects=False)
    
    # If SessionMiddleware is missing, this would be 500
    assert response.status_code == 307
