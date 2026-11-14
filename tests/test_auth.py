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


def test_bearer_token_fallback(client, user1, token_user1):
    """Verifies that Authorization: Bearer token is supported as fallback for mobile/APIs."""
    response = client.get("/auth/me", headers={"Authorization": f"Bearer {token_user1}"})
    assert response.status_code == 200
    assert response.json()["id"] == user1.id


def test_cors_allows_arbitrary_localhost_with_credentials(client):
    """Verifies that CORS allows arbitrary localhost ports with credentials mode enabled."""
    response = client.get(
        "/auth/health",
        headers={"Origin": "http://localhost:54321"}
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:54321"
    assert response.headers.get("access-control-allow-credentials") == "true"


from unittest.mock import patch

def test_full_google_oauth_web_redirect_and_cookies(client, db):
    """Verifies that google/callback redirects to target_url and sets HttpOnly cookies."""
    # Step 1: user visits /auth/google/login?redirect_url=http://localhost:54321
    login_resp = client.get("/auth/google/login?redirect_url=http://localhost:54321", follow_redirects=False)
    assert login_resp.status_code == 302
    assert "accounts.google.com" in login_resp.headers["location"]

    # Step 2: Google redirects back to /auth/google/callback
    with patch("app.Oauth.oauth.google.authorize_access_token") as mock_token:
        mock_token.return_value = {
            "userinfo": {
                "sub": "gid_web_999",
                "name": "Web User",
                "email": "webuser@example.com"
            }
        }
        cb_resp = client.get("/auth/google/callback", follow_redirects=False)
        assert cb_resp.status_code == 302
        assert cb_resp.headers["location"] == "http://localhost:54321"
        assert "access_token" in cb_resp.cookies
        assert "refresh_token" in cb_resp.cookies

        # Step 3: client loads /auth/me with cookies
        me_resp = client.get("/auth/me", cookies=cb_resp.cookies)
        print("ME RESP JSON:", me_resp.json())
        assert me_resp.status_code == 200
        assert me_resp.json()["email"] == "webuser@example.com"

        # Step 4: client refreshes token
        ref_resp = client.post("/auth/refresh", cookies=cb_resp.cookies)
        assert ref_resp.status_code == 200
        assert "access_token" in ref_resp.cookies

        # Step 5: client logs out
        logout_resp = client.post("/auth/Logout", cookies=cb_resp.cookies)
        assert logout_resp.status_code == 200
