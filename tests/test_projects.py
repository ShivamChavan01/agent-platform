from conftest import auth_headers, register

PROJECT = {
    "name": "Support Bot",
    "description": "answers FAQs",
    "system_prompt": "You are a helpful support agent.",
    "model": "deepseek/deepseek-v4-flash",
}


def create_project(client, token, **overrides):
    return client.post(
        "/projects",
        headers=auth_headers(token),
        json={**PROJECT, **overrides},
    )


def test_create_project(client):
    token = register(client).json()["access_token"]
    resp = create_project(client, token)
    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "Support Bot"
    assert body["system_prompt"] == PROJECT["system_prompt"]
    assert body["model"] == PROJECT["model"]
    assert body["user_id"]


def test_create_project_defaults_model(client):
    token = register(client).json()["access_token"]
    resp = create_project(client, token, model=None)
    assert resp.status_code == 201
    assert resp.json()["model"] == "deepseek/deepseek-v4-flash"


def test_list_projects_only_shows_own(client):
    token_a = register(client, email="a@example.com").json()["access_token"]
    create_project(client, token_a, name="Mine")
    token_b = register(client, email="b@example.com").json()["access_token"]
    create_project(client, token_b, name="Theirs")

    mine = client.get("/projects", headers=auth_headers(token_a)).json()
    assert [p["name"] for p in mine] == ["Mine"]


def test_get_project_other_user_404(client):
    token_a = register(client, email="a@example.com").json()["access_token"]
    pid = create_project(client, token_a).json()["id"]
    token_b = register(client, email="b@example.com").json()["access_token"]

    resp = client.get(f"/projects/{pid}", headers=auth_headers(token_b))
    assert resp.status_code == 404
    assert resp.json() == {"error": "Project not found"}


def test_update_project_partial(client):
    token = register(client).json()["access_token"]
    pid = create_project(client, token).json()["id"]

    resp = client.patch(
        f"/projects/{pid}",
        headers=auth_headers(token),
        json={"name": "Renamed Bot"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "Renamed Bot"
    assert body["system_prompt"] == PROJECT["system_prompt"]


def test_update_project_other_user_404(client):
    token_a = register(client, email="a@example.com").json()["access_token"]
    pid = create_project(client, token_a).json()["id"]
    token_b = register(client, email="b@example.com").json()["access_token"]

    resp = client.patch(
        f"/projects/{pid}", headers=auth_headers(token_b), json={"name": "Hijack"}
    )
    assert resp.status_code == 404


def test_delete_project_then_get_404(client):
    token = register(client).json()["access_token"]
    pid = create_project(client, token).json()["id"]

    assert client.delete(f"/projects/{pid}", headers=auth_headers(token)).status_code == 204
    assert client.get(f"/projects/{pid}", headers=auth_headers(token)).status_code == 404
