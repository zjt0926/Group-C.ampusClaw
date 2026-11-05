def _first_wrong(client, subject="数学"):
    response = client.get(f"/api/wrong-questions?subject={subject}")
    assert response.status_code == 200
    items = response.get_json()["items"]
    assert items
    return items[0]


def _set_skill(client, skill_key, payload):
    response = client.put(f"/api/teacher/skills/{skill_key}", json=payload)
    assert response.status_code == 200
    return response.get_json()["skill"]


def test_wrong_explain_three_sections_and_cache(student_client, teacher_client):
    wrong = _first_wrong(student_client)
    first = student_client.post(f"/api/wrong-questions/{wrong['id']}/explain")
    assert first.status_code == 200
    body = first.get_json()
    assert body["cached"] is False
    explanation = body["explanation"]
    assert explanation["error_analysis"]
    assert explanation["advice"]
    assert explanation["knowledge_points"]
    assert explanation["no_hit"] is False
    point = explanation["knowledge_points"][0]
    assert point["material_title"] == "一元二次方程与求根公式"
    assert point["chunk_no"]

    second = student_client.post(f"/api/wrong-questions/{wrong['id']}/explain")
    assert second.status_code == 200
    assert second.get_json()["cached"] is True
    assert second.get_json()["explanation"] == explanation

    summary = teacher_client.get("/api/teacher/audit/summary").get_json()
    skills = {item["skill"]: item for item in summary["skills"]}
    assert "wrong_explain" in skills
    assert skills["wrong_explain"]["count"] >= 1
    assert skills["wrong_explain"]["fail_rate"] == 0.0


def test_wrong_explain_is_isolated(student_client, student2_client, b_client):
    wrong = _first_wrong(student_client)

    response = student2_client.post(f"/api/wrong-questions/{wrong['id']}/explain")
    assert response.status_code == 404
    assert response.get_json()["error_code"] == "not_found"

    response = b_client.post(f"/api/wrong-questions/{wrong['id']}/explain")
    assert response.status_code == 404

    assert student2_client.get("/api/wrong-questions?subject=数学").get_json()["items"] == []
    assert b_client.get("/api/wrong-questions?subject=数学").get_json()["items"] == []


def test_wrong_explain_disabled_returns_409(student_client, teacher_client):
    _set_skill(teacher_client, "wrong_explain", {"enabled": False})
    wrong = _first_wrong(student_client)
    response = student_client.post(f"/api/wrong-questions/{wrong['id']}/explain")
    assert response.status_code == 409
    assert response.get_json()["error_code"] == "skill_disabled"


def test_care_risk_message_returns_safety_channels(student_client, teacher_client):
    response = student_client.post("/api/care/chat", json={"message": "我不想活了"})
    assert response.status_code == 200
    body = response.get_json()
    assert body["risk"] is True
    assert body["mode"] == "safety"
    assert "12356" in body["reply"]["content"]
    assert "12356" in " ".join(body["help_channels"])

    history = student_client.get("/api/care/history")
    assert history.status_code == 200
    items = history.get_json()["items"]
    assert len(items) == 2
    assert items[0]["role"] == "user"
    assert items[0]["safety"] is True
    assert items[1]["role"] == "assistant"
    assert items[1]["safety"] is True

    summary = teacher_client.get("/api/teacher/audit/summary").get_json()
    skills = {item["skill"]: item for item in summary["skills"]}
    assert skills["care_chat"]["count"] >= 1


def test_care_normal_message_and_isolation(student_client, student2_client):
    response = student_client.post("/api/care/chat", json={"message": "最近考试压力有点大"})
    assert response.status_code == 200
    body = response.get_json()
    assert body["risk"] is False
    assert body["mode"] == "local-demo"
    assert body["reply"]

    assert student2_client.get("/api/care/history").get_json()["items"] == []


def test_care_disabled_returns_409(student_client, teacher_client):
    _set_skill(teacher_client, "care_chat", {"enabled": False})

    response = student_client.get("/api/care/history")
    assert response.status_code == 409
    body = response.get_json()
    assert body["error_code"] == "skill_disabled"
    assert body["help_channels"]

    response = student_client.post("/api/care/chat", json={"message": "我想聊聊"})
    assert response.status_code == 409
    assert response.get_json()["error_code"] == "skill_disabled"


def test_care_rejects_invalid_message(student_client):
    response = student_client.post("/api/care/chat", json={"message": "   "})
    assert response.status_code == 400
    assert response.get_json()["error_code"] == "invalid_message"

    response = student_client.post("/api/care/chat", json={"message": "x" * 1001})
    assert response.status_code == 400
    assert response.get_json()["error_code"] == "invalid_message"
