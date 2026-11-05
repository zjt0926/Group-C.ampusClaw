from flask import Blueprint, g, jsonify, request

from ..adapters.ai_gateway import is_configured, masked_key
from ..auth import json_error, login_required, role_required
from ..extensions import db
from ..models import McpServer, Skill
from ..services.skills import list_student_skills

bp = Blueprint("assistant_api", __name__, url_prefix="/api")


@bp.get("/skills")
@role_required("student")
def student_skills():
    return jsonify({"items": list_student_skills(g.current_user.class_id)})


@bp.put("/skills/<skill_key>")
@login_required
def student_write_forbidden(skill_key):
    if g.current_user.role != "teacher":
        return json_error("学生不能修改技能配置", 403, "forbidden")
    return json_error("请使用教师技能配置接口", 400, "wrong_endpoint")


@bp.get("/teacher/skills")
@role_required("teacher")
def teacher_skills():
    skills = (
        Skill.query.filter_by(class_id=g.current_user.class_id)
        .order_by(Skill.id.asc())
        .all()
    )
    return jsonify({"items": [skill.to_dict(include_prompt=True) for skill in skills]})


@bp.put("/teacher/skills/<skill_key>")
@role_required("teacher")
def update_skill(skill_key):
    skill = Skill.query.filter_by(
        class_id=g.current_user.class_id, skill_key=skill_key
    ).first()
    if skill is None:
        return json_error("技能不存在", 404, "not_found")
    payload = request.get_json(silent=True) or {}

    if "enabled" in payload:
        enabled = bool(payload["enabled"])
        if skill.required and not enabled:
            return json_error("必做技能不能停用", 400, "required_skill")
        skill.enabled = enabled
    if "prompt" in payload:
        prompt = str(payload["prompt"])
        if len(prompt) > 5000:
            return json_error("提示词不能超过 5000 字符", 400, "invalid_prompt")
        skill.prompt = prompt
    if "trigger_condition" in payload:
        skill.trigger_condition = str(payload["trigger_condition"])[:200]
    if "behavior" in payload:
        skill.behavior = str(payload["behavior"])[:300]

    db.session.commit()
    return jsonify({"skill": skill.to_dict(include_prompt=True)})


@bp.get("/teacher/config")
@role_required("teacher")
def teacher_config():
    return jsonify(
        {
            "api_key_masked": masked_key(),
            "ai_mode": "gateway" if is_configured() else "local-demo",
        }
    )


@bp.get("/teacher/mcp-servers")
@role_required("teacher")
def mcp_servers():
    items = (
        McpServer.query.filter_by(class_id=g.current_user.class_id)
        .order_by(McpServer.id.asc())
        .all()
    )
    return jsonify({"items": [item.to_dict() for item in items]})


@bp.post("/teacher/mcp-servers")
@role_required("teacher")
def add_mcp_server():
    payload = request.get_json(silent=True) or {}
    name = str(payload.get("name", "")).strip()
    url = str(payload.get("url", "")).strip()
    if not name or len(name) > 80:
        return json_error("服务器名称必须为 1—80 字符", 400, "invalid_name")
    if not url or len(url) > 200:
        return json_error("服务器地址不合法", 400, "invalid_url")
    server = McpServer(
        class_id=g.current_user.class_id,
        name=name,
        url=url,
        status="connecting",
        tools="[]",
    )
    db.session.add(server)
    db.session.commit()
    # 演示接入：模拟一次握手，发现两个工具
    server.status = "connected"
    server.tools = '["kb.search","kb.getChunk"]'
    db.session.commit()
    return jsonify({"server": server.to_dict()}), 201


@bp.post("/teacher/mcp-servers/<int:server_id>/connect")
@role_required("teacher")
def connect_server(server_id):
    server = McpServer.query.filter_by(
        id=server_id, class_id=g.current_user.class_id
    ).first()
    if server is None:
        return json_error("服务器不存在", 404, "not_found")
    server.status = "connected"
    if not server.tools or server.tools == "[]":
        server.tools = '["kb.search","kb.getChunk"]'
    db.session.commit()
    return jsonify({"server": server.to_dict()})


@bp.post("/teacher/mcp-servers/<int:server_id>/disconnect")
@role_required("teacher")
def disconnect_server(server_id):
    server = McpServer.query.filter_by(
        id=server_id, class_id=g.current_user.class_id
    ).first()
    if server is None:
        return json_error("服务器不存在", 404, "not_found")
    server.status = "disconnected"
    db.session.commit()
    return jsonify({"server": server.to_dict()})


@bp.delete("/teacher/mcp-servers/<int:server_id>")
@role_required("teacher")
def delete_server(server_id):
    server = McpServer.query.filter_by(
        id=server_id, class_id=g.current_user.class_id
    ).first()
    if server is None:
        return json_error("服务器不存在", 404, "not_found")
    db.session.delete(server)
    db.session.commit()
    return jsonify({"ok": True})
