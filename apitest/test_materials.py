def test_teacher_creates_material_and_student_reads_it(teacher_client, student_client):
    response = teacher_client.post(
        "/api/teacher/materials",
        json={
            "subject": "语文",
            "title": "测试讲义·修辞手法",
            "content": "比喻是用相似事物打比方。\n拟人是把物当作人来写。",
        },
    )
    assert response.status_code == 201
    material = response.get_json()["material"]
    assert material["chunk_count"] == 2
    assert material["subject"] == "语文"

    response = student_client.get("/api/materials?subject=语文")
    assert response.status_code == 200
    items = response.get_json()["items"]
    assert any(item["id"] == material["id"] for item in items)
    assert response.get_json()["total"] == len(items)


def test_student_search_returns_real_sources(student_client):
    response = student_client.get("/api/materials/search?subject=数学&q=求根公式")
    assert response.status_code == 200
    body = response.get_json()
    assert body["matched"] is True
    assert body["total"] >= 1
    hit = body["items"][0]
    assert hit["material_title"] == "一元二次方程与求根公式"
    assert isinstance(hit["chunk_no"], int)
    assert hit["relevance"] > 0
    assert hit["text"]


def test_student_search_miss_returns_empty(student_client):
    response = student_client.get("/api/materials/search?subject=数学&q=量子纠缠XYZ")
    assert response.status_code == 200
    body = response.get_json()
    assert body["matched"] is False
    assert body["items"] == []
    assert body["total"] == 0


def test_invalid_subject_rejected(student_client):
    response = student_client.get("/api/materials?subject=生物")
    assert response.status_code == 400
    assert response.get_json()["error_code"] == "invalid_subject"


def test_student_cannot_create_material(student_client):
    response = student_client.post(
        "/api/teacher/materials",
        json={"subject": "数学", "title": "非法", "content": "内容"},
    )
    assert response.status_code == 403


def test_cross_class_material_detail_is_404(student_client, b_client):
    response = student_client.get("/api/materials?subject=数学")
    material_id = response.get_json()["items"][0]["id"]

    response = b_client.get(f"/api/materials/{material_id}")
    assert response.status_code == 404
    assert response.get_json()["error_code"] == "not_found"


def test_teacher_delete_material_removes_it(teacher_client, student_client):
    response = teacher_client.post(
        "/api/teacher/materials",
        json={"subject": "英语", "title": "待删除讲义", "content": "一行内容"},
    )
    material_id = response.get_json()["material"]["id"]

    response = teacher_client.delete(f"/api/teacher/materials/{material_id}")
    assert response.status_code == 200
    assert response.get_json()["ok"] is True

    response = student_client.get(f"/api/materials/{material_id}")
    assert response.status_code == 404
