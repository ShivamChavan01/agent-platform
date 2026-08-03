from conftest import auth_headers, register


def test_register_returns_token_and_user(client):
    resp = register(client)
    assert resp.status_code == 201
    body = resp.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["user"]["email"] == "user@example.com"
    assert body["user"]["id"]


def test_register_duplicate_email_conflicts(client):
    assert register(client).status_code == 201
    resp = register(client)
    assert resp.status_code == 409
    assert resp.json() == {"error": "Email already registered"}


def test_register_short_password_rejected(client):
    resp = register(client, password="short")
    assert resp.status_code == 422
    assert "error" in resp.json()


def test_login_returns_token(client):
    register(client)
    resp = client.post(
        "/auth/login", json={"email": "user@example.com", "password": "password123"}
    )
    assert resp.status_code == 200
    assert resp.json()["access_token"]


def test_login_wrong_password_unauthorized(client):
    register(client)
    resp = client.post(
        "/auth/login", json={"email": "user@example.com", "password": "wrong-pass"}
    )
    assert resp.status_code == 401
    assert resp.json() == {"error": "Invalid email or password"}


def test_login_unknown_email_unauthorized(client):
    resp = client.post(
        "/auth/login", json={"email": "nobody@example.com", "password": "password123"}
    )
    assert resp.status_code == 401
    assert resp.json() == {"error": "Invalid email or password"}


def test_protected_route_without_token_unauthorized(client):
    assert client.get("/projects").status_code == 401


def test_password_stored_hashed(client, db_session):
    register(client)
    from app.models import User

    user = db_session.query(User).filter_by(email="user@example.com").one()
    assert user.hashed_password != "password123"
    assert user.hashed_password.startswith("$2b$")
