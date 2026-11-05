import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

PASSWORD = "Campus@123"


@pytest.fixture()
def app(tmp_path, monkeypatch):
    os.environ["CELERY_ALWAYS_EAGER"] = "1"
    monkeypatch.setenv("CELERY_ALWAYS_EAGER", "1")

    from app import create_app
    from app.config import Config
    from app.extensions import db
    from app.seed import seed

    Config.DATABASE_URL = f"sqlite:///{tmp_path / 'test.db'}"
    Config.SQLALCHEMY_DATABASE_URI = Config.DATABASE_URL
    Config.AI_GATEWAY_BASE_URL = ""
    Config.AI_GATEWAY_API_KEY = ""
    Config.TESTING = True
    Config.SECRET_KEY = "test-secret"
    Config.JWT_SECRET = "test-jwt-secret"

    application = create_app(Config)
    application.config.update(
        TESTING=True,
        AI_GATEWAY_BASE_URL="",
        AI_GATEWAY_API_KEY="",
    )
    with application.app_context():
        db.drop_all()
        db.create_all()
        seed()

    yield application

    with application.app_context():
        db.session.remove()
        db.drop_all()


def login(client, username, password=PASSWORD):
    return client.post("/api/auth/login", json={"username": username, "password": password})


@pytest.fixture()
def anon_client(app):
    return app.test_client()


@pytest.fixture()
def teacher_client(app):
    client = app.test_client()
    response = login(client, "teacher_a")
    assert response.status_code == 200
    return client


@pytest.fixture()
def student_client(app):
    client = app.test_client()
    response = login(client, "student_a1")
    assert response.status_code == 200
    return client


@pytest.fixture()
def student2_client(app):
    client = app.test_client()
    response = login(client, "student_a2")
    assert response.status_code == 200
    return client


@pytest.fixture()
def b_client(app):
    client = app.test_client()
    response = login(client, "student_b1")
    assert response.status_code == 200
    return client
