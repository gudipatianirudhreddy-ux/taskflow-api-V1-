from datetime import timedelta
from app.auth import access_token, create_refresh_token, get_current_user
from app.main import app


def test_missing_credentials_returns_401(client):
    """Requesting protected route without access_token cookie returns 401."""
    response = client.get("/tasks/")
    assert response.status_code == 401
    assert response.json()["detail"] == "Missing token"


def test_invalid_jwt_signature_returns_401(client):
    """Requesting protected route with an invalid JWT string returns 401."""
    client.cookies.set("access_token", "invalid.jwt.token")
    response = client.get("/tasks/")
    assert response.status_code == 401
    assert response.json()["detail"] == "Could not validate user"


def test_refresh_token_as_access_token_returns_401(client, user1):
    """Using a refresh token where an access token is expected returns 401."""
    ref_token = create_refresh_token(username=user1.username, id=user1.id, expires_delta=timedelta(days=7))
    client.cookies.set("access_token", ref_token)
    response = client.get("/tasks/")
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid access token"


def test_auth_me_with_valid_credentials(auth_client_user1, user1):
    """GET /auth/me returns the authenticated user info."""
    response = auth_client_user1.get("/auth/me")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == user1.id
    assert data["email"] == user1.email


def test_auth_me_with_dependency_override(client, user2):
    """Verifies that dependency override for get_current_user works as required."""
    app.dependency_overrides[get_current_user] = lambda: {"username": user2.username, "id": user2.id}
    try:
        response = client.get("/auth/me")
        assert response.status_code == 200
        assert response.json()["id"] == user2.id
        assert response.json()["email"] == user2.email
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_auth_refresh_token_endpoint(client, user1):
    """POST /auth/refresh with valid refresh token sets new access_token cookie."""
    ref_token = create_refresh_token(username=user1.username, id=user1.id, expires_delta=timedelta(days=7))
    client.cookies.set("refresh_token", ref_token)
    response = client.post("/auth/refresh")
    assert response.status_code == 200
    assert response.json()["message"] == "Access token refreshed successfully"
    assert "access_token" in response.cookies


def test_auth_logout_clears_cookies(auth_client_user1):
    """POST /auth/Logout removes access and refresh tokens."""
    response = auth_client_user1.post("/auth/Logout")
    assert response.status_code == 200
    assert response.json()["message"] == "Logged out successfully"
