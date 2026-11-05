from datetime import datetime, timedelta


def _first_assignment(client, subject="数学"):
    response = client.get(f"/api/assignments?subject={subject}")
    assert response.status_code == 200
    items = response.get_json()["items"]
    assert items
    return items[0]


def test_submit_runs_grading_and_creates_wrong_question(app, student_client):
    assignment = _first_assignment(student_client)
    response = student_client.post(
        f"/api/assignments/{assignment['id']}/submit",
        json={"content": "x=2", "idempotency_key": "api-test-short-answer"},
    )
    assert response.status_code == 202
    submission_id = response.get_json()["submission_id"]

    response = student_client.get(f"/api/submissions/{submission_id}")
    assert response.status_code == 200
    submission = response.get_json()["submission"]
    assert submission["status"] == "graded"
    assert submission["ai_score"] == 45
    assert submission["ai_comment"]
    assert submission["ai_evidence"]
    for item in submission["ai_evidence"]:
        assert item["material_title"] == "一元二次方程与求根公式"
        assert item["chunk_no"]

    with app.app_context():
        from app.models import Submission, WrongQuestion

        row = Submission.query.filter_by(id=submission_id).first()
        assert row.status == "graded"
        assert row.graded_at is not None
        wrong = WrongQuestion.query.filter_by(submission_id=submission_id).first()
        assert wrong is not None
        assert wrong.error_reason


def test_submit_is_idempotent(student_client):
    assignment = _first_assignment(student_client)
    payload = {"content": "x=2", "idempotency_key": "api-test-idempotent"}
    first = student_client.post(f"/api/assignments/{assignment['id']}/submit", json=payload)
    assert first.status_code == 202
    second = student_client.post(f"/api/assignments/{assignment['id']}/submit", json=payload)
    assert second.status_code == 200
    assert second.get_json()["submission_id"] == first.get_json()["submission_id"]


def test_submit_rejects_invalid_payload(student_client):
    assignment = _first_assignment(student_client)
    response = student_client.post(
        f"/api/assignments/{assignment['id']}/submit",
        json={"content": "", "idempotency_key": "empty-content"},
    )
    assert response.status_code == 400
    assert response.get_json()["error_code"] == "invalid_content"

    response = student_client.post(
        f"/api/assignments/{assignment['id']}/submit",
        json={"content": "x=2", "idempotency_key": ""},
    )
    assert response.status_code == 400
    assert response.get_json()["error_code"] == "invalid_key"


def test_submit_after_deadline_is_rejected(teacher_client, student_client):
    past = (datetime.utcnow() - timedelta(minutes=2)).isoformat()
    response = teacher_client.post(
        "/api/assignments",
        json={
            "subject": "化学",
            "title": "已截止作业",
            "description": "过期作业",
            "deadline": past,
        },
    )
    assert response.status_code == 201
    assignment_id = response.get_json()["assignment"]["id"]

    response = student_client.post(
        f"/api/assignments/{assignment_id}/submit",
        json={"content": "任意作答", "idempotency_key": "closed-assignment"},
    )
    assert response.status_code == 409
    assert response.get_json()["error_code"] == "assignment_closed"


def test_submission_stream_closes_on_terminal_state(student_client):
    assignment = _first_assignment(student_client)
    response = student_client.post(
        f"/api/assignments/{assignment['id']}/submit",
        json={"content": "x=2", "idempotency_key": "api-test-stream"},
    )
    submission_id = response.get_json()["submission_id"]

    stream = student_client.get(f"/api/submissions/{submission_id}/stream")
    assert stream.status_code == 200
    text = stream.get_data(as_text=True)
    assert "event: status" in text
    assert '"status": "graded"' in text


def test_submission_detail_cross_class_404(student_client, b_client):
    assignment = _first_assignment(student_client)
    response = student_client.post(
        f"/api/assignments/{assignment['id']}/submit",
        json={"content": "x=2", "idempotency_key": "api-test-cross-class"},
    )
    submission_id = response.get_json()["submission_id"]

    response = b_client.get(f"/api/submissions/{submission_id}")
    assert response.status_code == 404
    assert "submission" not in response.get_json()
