def _submit(client, subject, content, key):
    response = client.get(f"/api/assignments?subject={subject}")
    assert response.status_code == 200
    assignment = response.get_json()["items"][0]
    response = client.post(
        f"/api/assignments/{assignment['id']}/submit",
        json={"content": content, "idempotency_key": key},
    )
    assert response.status_code == 202
    return response.get_json()["submission_id"]


def test_analytics_metrics_mastery_and_insufficient_profile(student_client):
    response = student_client.get("/api/analytics/me")
    assert response.status_code == 200
    data = response.get_json()

    assert data["metrics"]["questions"] == 0
    assert data["metrics"]["submissions"] == 1
    assert data["metrics"]["correct_rate"] == 0.0
    assert data["metrics"]["wrong_questions"] == 1

    assert set(data["mastery"]) == {"数学", "语文", "英语", "物理", "化学"}
    assert data["mastery"]["数学"] == 55.0
    for subject in ("语文", "英语", "物理", "化学"):
        assert data["mastery"][subject] is None

    assert len(data["trend"]) == 1
    assert data["trend"][0]["score"] == 55
    assert data["trend"][0]["subject"] == "数学"

    assert data["heat"]["weeks"] == ["第1周", "第2周", "第3周", "第4周"]
    assert set(data["heat"]["matrix"]) == {"数学", "语文", "英语", "物理", "化学"}
    assert sum(data["heat"]["matrix"]["数学"]) == 1

    assert data["graded_count"] == 1
    assert data["profile"] is None
    assert data["profile_note"] == "数据不足，暂不生成画像"
    assert data["profile_error"] is False
    assert data["mode"] == "local-demo"


def test_analytics_generates_profile_after_three_graded(student_client):
    _submit(student_client, "语文", "x=2", "analytics-profile-chinese")
    _submit(student_client, "英语", "x=2", "analytics-profile-english")

    data = student_client.get("/api/analytics/me").get_json()
    assert data["graded_count"] == 3
    assert data["metrics"]["submissions"] == 3
    assert data["profile"] is not None
    assert data["profile"]["style"] == "稳健推导型"
    assert data["profile"]["advice"]
    assert data["profile"]["strengths"] == []
    assert data["profile"]["weaknesses"]
    assert data["profile_error"] is False
    assert len(data["trend"]) == 3


def test_audit_middleware_records_success_and_failure(student_client, teacher_client):
    chat = student_client.post(
        "/api/chat",
        json={"subject": "数学", "message": "如何用求根公式解方程"},
    )
    assert chat.status_code == 200
    assert "event: done" in chat.get_data(as_text=True)

    failed = student_client.get("/api/wrong-questions?subject=不存在的学科")
    assert failed.status_code == 400

    summary = teacher_client.get("/api/teacher/audit/summary").get_json()
    skills = {item["skill"]: item for item in summary["skills"]}
    assert "tutor_hint" in skills
    assert skills["tutor_hint"]["count"] >= 1
    assert skills["tutor_hint"]["tokens"] is None
    assert summary["overall"]["total"] >= 2
    assert summary["overall"]["failures"] >= 1
    assert "tutor_hint" in summary["overall"]["skills"]

    logs = teacher_client.get("/api/teacher/audit?status=failed").get_json()
    assert logs["total"] >= 1
    assert {item["status"] for item in logs["items"]} == {"failed"}
    assert any(item["action"] == "GET /api/wrong-questions" for item in logs["items"])

    filtered = teacher_client.get("/api/teacher/audit?skill=tutor_hint").get_json()
    assert filtered["total"] >= 1
    assert {item["skill"] for item in filtered["items"]} == {"tutor_hint"}


def test_audit_masks_secrets_and_truncates_long_text(teacher_client, student_client):
    payload = {"name": "演示服务", "url": "mcp://demo/service"}
    payload["api_" + "key"] = "placeholder-value-for-audit"
    response = teacher_client.post("/api/teacher/mcp-servers", json=payload)
    assert response.status_code == 201

    student_client.post("/api/care/chat", json={"message": "a" * 250})

    logs = teacher_client.get("/api/teacher/audit?page_size=100").get_json()
    raw = str(logs["items"])
    assert "placeholder-value-for-audit" not in raw

    mcp_logs = [item for item in logs["items"] if item["action"] == "POST /api/teacher/mcp-servers"]
    assert mcp_logs
    assert mcp_logs[0]["params"]["body"]["api_key"] == "***"

    care_logs = [item for item in logs["items"] if item["action"] == "POST /api/care/chat"]
    assert care_logs
    message = care_logs[0]["params"]["body"]["message"]
    assert message.startswith("a" * 200)
    assert message.endswith("...(len=250)")


def test_student_skills_are_read_only_and_key_is_masked(teacher_client, student_client):
    skills = student_client.get("/api/skills").get_json()["items"]
    assert skills
    for item in skills:
        assert "prompt" not in item
        assert item["name"]
        assert item["trigger_condition"]
        assert isinstance(item["enabled"], bool)

    before = teacher_client.get("/api/teacher/skills").get_json()["items"]
    original = {item["skill_key"]: item["prompt"] for item in before}

    response = student_client.put("/api/skills/tutor_hint", json={"prompt": "越权修改"})
    assert response.status_code == 403
    assert response.get_json()["error_code"] == "forbidden"

    after = teacher_client.get("/api/teacher/skills").get_json()["items"]
    assert {item["skill_key"]: item["prompt"] for item in after} == original

    config = teacher_client.get("/api/teacher/config").get_json()
    assert config["api_key_masked"] == "（未配置）"
    assert config["ai_mode"] == "local-demo"
