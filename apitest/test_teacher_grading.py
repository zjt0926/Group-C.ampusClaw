from werkzeug.security import generate_password_hash

from .conftest import login


def _submissions(client, subject="数学"):
    response = client.get(f"/api/teacher/submissions?subject={subject}")
    assert response.status_code == 200
    return response.get_json()


def _by_student(items, student_id):
    for item in items:
        if item["student_id"] == student_id:
            return item
    raise AssertionError(f"未找到 {student_id} 的提交")


def _make_teacher_b(app):
    with app.app_context():
        from app.extensions import db
        from app.models import User

        if User.query.filter_by(username="teacher_b").first() is None:
            db.session.add(
                User(
                    id="u-teacher-b",
                    username="teacher_b",
                    password_hash=generate_password_hash("Campus@123"),
                    display_name="李老师",
                    role="teacher",
                    class_id="cls-b",
                )
            )
            db.session.commit()


def test_teacher_lists_only_own_class(teacher_client, app):
    data = _submissions(teacher_client)
    assert data["total"] == 2
    assert {item["student_id"] for item in data["items"]} == {"u-stu-a1", "u-stu-a2"}
    for item in data["items"]:
        assert item["student_name"]
        assert item["content"]
        assert item["status"] == "graded"
        assert item["ai_score"] is not None
        assert item["teacher_score"] is None

    _make_teacher_b(app)
    other = app.test_client()
    assert login(other, "teacher_b").status_code == 200
    other_data = _submissions(other)
    assert other_data["total"] == 0
    assert other_data["items"] == []

    # 参数里的 class_id 必须被忽略
    response = other.get("/api/teacher/submissions?subject=数学&class_id=cls-a")
    assert response.status_code == 200
    assert response.get_json()["total"] == 0


def test_override_keeps_ai_fields_and_is_visible_to_student(teacher_client, student_client):
    submission = _by_student(_submissions(teacher_client)["items"], "u-stu-a1")
    original_ai_score = submission["ai_score"]
    original_ai_comment = submission["ai_comment"]

    response = teacher_client.patch(
        f"/api/submissions/{submission['id']}/score",
        json={"teacher_score": 88, "teacher_comment": "思路完整，终评为 88 分。"},
    )
    assert response.status_code == 200
    updated = response.get_json()["submission"]
    assert updated["teacher_score"] == 88
    assert updated["final_score"] == 88
    assert updated["ai_score"] == original_ai_score
    assert updated["ai_comment"] == original_ai_comment

    response = student_client.get(f"/api/submissions/{submission['id']}")
    assert response.status_code == 200
    seen = response.get_json()["submission"]
    assert seen["teacher_score"] == 88
    assert seen["teacher_comment"] == "思路完整，终评为 88 分。"
    assert seen["ai_score"] == original_ai_score
    assert seen["final_score"] == 88

    logs = teacher_client.get("/api/teacher/audit?page_size=100").get_json()
    overrides = [item for item in logs["items"] if item["action"] == "grade_override"]
    assert overrides
    params = overrides[0]["params"]
    assert params["submission_id"] == submission["id"]
    assert params["old_score"] is None
    assert params["new_score"] == 88
    assert params["new_comment"] == "思路完整，终评为 88 分。"


def test_override_rejects_invalid_params_and_pending(teacher_client, app):
    submission = _by_student(_submissions(teacher_client)["items"], "u-stu-a2")

    response = teacher_client.patch(
        f"/api/submissions/{submission['id']}/score",
        json={"teacher_score": 101, "teacher_comment": "越界"},
    )
    assert response.status_code == 400
    assert response.get_json()["error_code"] == "invalid_score"

    response = teacher_client.patch(
        f"/api/submissions/{submission['id']}/score",
        json={"teacher_score": 88, "teacher_comment": "x" * 501},
    )
    assert response.status_code == 400
    assert response.get_json()["error_code"] == "invalid_comment"

    with app.app_context():
        from app.extensions import db
        from app.models import Submission

        assert db.session.get(Submission, submission["id"]).teacher_score is None

        assignment_id = submission["assignment_id"]
        pending = Submission(
            assignment_id=assignment_id,
            student_id="u-stu-a1",
            class_id="cls-a",
            content="等待批改的作答",
            status="pending",
            idempotency_key="pending-override-test",
        )
        db.session.add(pending)
        db.session.commit()
        pending_id = pending.id

    response = teacher_client.patch(
        f"/api/submissions/{pending_id}/score",
        json={"teacher_score": 70, "teacher_comment": "未批改不给分"},
    )
    assert response.status_code == 409
    assert response.get_json()["error_code"] == "not_graded"


def test_override_permissions(teacher_client, student_client, anon_client, app):
    submission = _by_student(_submissions(teacher_client)["items"], "u-stu-a2")
    url = f"/api/submissions/{submission['id']}/score"

    response = student_client.patch(url, json={"teacher_score": 99, "teacher_comment": "越权"})
    assert response.status_code == 403
    assert response.get_json()["error_code"] == "forbidden"

    response = anon_client.patch(url, json={"teacher_score": 99})
    assert response.status_code == 401

    _make_teacher_b(app)
    other = app.test_client()
    assert login(other, "teacher_b").status_code == 200
    response = other.patch(url, json={"teacher_score": 99, "teacher_comment": "跨班"})
    assert response.status_code == 404
    assert response.get_json()["error_code"] == "not_found"

    with app.app_context():
        from app.extensions import db
        from app.models import Submission

        assert db.session.get(Submission, submission["id"]).teacher_score is None


def test_mark_wrong_is_idempotent_and_undo_removes_it(teacher_client, student2_client):
    submission = _by_student(_submissions(teacher_client)["items"], "u-stu-a2")
    assert submission["is_wrong"] is False

    response = teacher_client.post(f"/api/submissions/{submission['id']}/mark-wrong")
    assert response.status_code == 200
    assert response.get_json()["submission"]["is_wrong"] is True

    items = student2_client.get("/api/wrong-questions?subject=数学").get_json()["items"]
    matched = [item for item in items if item["submission_id"] == submission["id"]]
    assert len(matched) == 1
    assert matched[0]["error_reason"].startswith("教师判定")

    response = teacher_client.post(f"/api/submissions/{submission['id']}/mark-wrong")
    assert response.status_code == 200
    items = student2_client.get("/api/wrong-questions?subject=数学").get_json()["items"]
    assert len([item for item in items if item["submission_id"] == submission["id"]]) == 1

    response = teacher_client.delete(f"/api/submissions/{submission['id']}/mark-wrong")
    assert response.status_code == 200
    assert response.get_json()["submission"]["is_wrong"] is False
    items = student2_client.get("/api/wrong-questions?subject=数学").get_json()["items"]
    assert [item for item in items if item["submission_id"] == submission["id"]] == []

    logs = teacher_client.get("/api/teacher/audit?page_size=100").get_json()
    actions = {item["action"] for item in logs["items"]}
    assert {"mark_wrong", "undo_mark_wrong"} <= actions
