from .conftest import login


def test_login_success_sets_http_only_cookie(anon_client):
    response = login(anon_client, "teacher_a")
    assert response.status_code == 200
    body = response.get_json()
    assert body["user"]["role"] == "teacher"
    assert body["user"]["class_id"] == "cls-a"
    cookie = response.headers.get("Set-Cookie", "")
    assert "access_token=" in cookie
    assert "HttpOnly" in cookie


def test_login_rejects_wrong_password(anon_client):
    response = login(anon_client, "teacher_a", "wrong-password")
    assert response.status_code == 401
    assert response.get_json()["error_code"] == "invalid_credentials"


def test_me_requires_login(anon_client):
    response = anon_client.get("/api/auth/me")
    assert response.status_code == 401
    assert response.get_json()["error_code"] == "unauthorized"


def test_me_returns_current_user(student_client):
    response = student_client.get("/api/auth/me")
    assert response.status_code == 200
    assert response.get_json()["user"]["username"] == "student_a1"


def test_role_pages_redirect(anon_client, student_client, teacher_client):
    response = anon_client.get("/teacher")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]

    response = student_client.get("/teacher")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/student")

    response = teacher_client.get("/student")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/teacher")


def test_student_teacher_api_forbidden(student_client):
    response = student_client.get("/api/teacher/submissions?subject=数学")
    assert response.status_code == 403
    assert response.get_json()["error_code"] == "forbidden"
