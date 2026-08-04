import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.embeddings import get_embedder
from app.main import app
from app.storage import get_storage

TEST_DATABASE_URL = "postgresql+psycopg2:///agent_platform_test"


class FakeStorage:
    def __init__(self):
        self.uploads = {}
        self.deletes = []

    def upload(self, path, data, content_type=None):
        self.uploads[path] = data

    def delete(self, path):
        self.deletes.append(path)
        self.uploads.pop(path, None)


class FakeEmbedder:
    def __init__(self, dim=768):
        self.dim = dim
        self.embed_documents_calls = []
        self.embed_query_calls = []

    def embed_documents(self, texts):
        self.embed_documents_calls.extend(texts)
        return [[0.01 * (i + 1)] * self.dim for i in range(len(texts))]

    def embed_query(self, text):
        self.embed_query_calls.append(text)
        return [0.5] * self.dim


@pytest.fixture
def fake_storage():
    return FakeStorage()


@pytest.fixture
def fake_embedder():
    return FakeEmbedder()


@pytest.fixture
def db_session():
    engine = create_engine(TEST_DATABASE_URL)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    engine.dispose()


@pytest.fixture
def client(db_session, fake_storage, fake_embedder):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_storage] = lambda: fake_storage
    app.dependency_overrides[get_embedder] = lambda: fake_embedder
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def register(client, email="user@example.com", password="password123", name=None):
    payload = {"email": email, "password": password}
    if name is not None:
        payload["name"] = name
    return client.post(
        "/auth/register", json=payload
    )


def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}
