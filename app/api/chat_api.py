import json
import time
from datetime import datetime

from flask import Blueprint, Response, current_app, g, jsonify, request, stream_with_context

from ..adapters import ai_gateway
from ..audit import record_skill
from ..auth import json_error, role_required, valid_subject
from ..extensions import db
from ..models import ChatMessage, SUBJECTS
from ..retrieval import search_chunks
from ..services.skills import get_skill, skill_enabled

bp = Blueprint("chat_api", __name__, url_prefix="/api")


@bp.get("/chat")
@role_required("student")
def chat_history():
    subject = request.args.get("subject", SUBJECTS[0])
    if not valid_subject(subject):
        return json_error("学科参数不合法", 400, "invalid_subject")
    messages = (
        ChatMessage.query.filter_by(
            class_id=g.current_user.class_id,
            student_id=g.current_user.id,
            subject=subject,
        )
        .order_by(ChatMessage.created_at.asc())
        .limit(60)
        .all()
    )
    return jsonify({"items": [message.to_dict() for message in messages], "subject": subject})


@bp.post("/chat")
@role_required("student")
def chat_stream():
    payload = request.get_json(silent=True) or {}
    subject = payload.get("subject")
    message = str(payload.get("message", "")).strip()
    if not valid_subject(subject):
        return json_error("学科参数不合法", 400, "invalid_subject")
    if not message or len(message) > 2000:
        return json_error("提问必须为 1—2000 字符", 400, "invalid_message")

    user = g.current_user
    user_message = ChatMessage(
        class_id=user.class_id,
        student_id=user.id,
        subject=subject,
        role="user",
        content=message,
    )
    db.session.add(user_message)
    db.session.commit()

    hits = search_chunks(user.class_id, subject, message)
    skill = get_skill(user.class_id, "tutor_hint")
    enabled = skill_enabled(user.class_id, "tutor_hint")
    route_name = skill.name if skill else "解题引导"
    started = datetime.utcnow()

    try:
        reply, tokens, mode = ai_gateway.tutor_reply(message, hits, enabled)
    except Exception as exc:  # noqa: BLE001
        reply = "抱歉，助手暂时无法回答。请稍后再试，或先查阅本班讲义。"
        tokens = None
        mode = "fallback"
        record_skill(
            user,
            "tutor_hint",
            "chat",
            "timeout" if isinstance(exc, ai_gateway.AIGatewayTimeout) else "error",
            (datetime.utcnow() - started).total_seconds() * 1000,
            None,
            {"subject": subject, "message": message},
        )

    trace = [
        {"label": "理解问题意图", "detail": "解析提问并规划步骤", "done": True},
        {
            "label": "检索班级知识库",
            "detail": f"命中 {len(hits)} 条片段" if hits else "无命中",
            "done": True,
        },
        {
            "label": "路由到技能",
            "detail": f"{route_name}（{'已开启' if enabled else '已关闭'}）",
            "done": True,
        },
        {"label": "组织并生成回答", "detail": f"{mode} 模式", "done": True},
        {"label": "流式输出中", "detail": "正在把回答推送到页面", "done": False},
    ]
    assistant = ChatMessage(
        class_id=user.class_id,
        student_id=user.id,
        subject=subject,
        role="assistant",
        content=reply,
        skill_key="tutor_hint",
        sources=json.dumps(hits, ensure_ascii=False),
        trace=json.dumps(trace, ensure_ascii=False),
    )
    db.session.add(assistant)
    db.session.commit()

    if mode != "fallback":
        record_skill(
            user,
            "tutor_hint",
            "chat",
            "success",
            (datetime.utcnow() - started).total_seconds() * 1000,
            tokens,
            {"subject": subject, "message": message},
        )

    def generate():
        yield f"event: trace\ndata: {json.dumps({'steps': trace, 'skill': route_name, 'enabled': enabled}, ensure_ascii=False)}\n\n"
        yield f"event: sources\ndata: {json.dumps(hits, ensure_ascii=False)}\n\n"
        buffer = ""
        for char in reply:
            buffer += char
            if len(buffer) >= 12:
                yield f"event: delta\ndata: {json.dumps({'text': buffer}, ensure_ascii=False)}\n\n"
                buffer = ""
                time.sleep(0.02)
        if buffer:
            yield f"event: delta\ndata: {json.dumps({'text': buffer}, ensure_ascii=False)}\n\n"
        yield (
            "event: done\ndata: "
            + json.dumps(
                {
                    "message_id": assistant.id,
                    "skill": route_name,
                    "mode": mode,
                    "matched": bool(hits),
                },
                ensure_ascii=False,
            )
            + "\n\n"
        )

    response = Response(stream_with_context(generate()), mimetype="text/event-stream")
    response.headers["Cache-Control"] = "no-cache"
    response.headers["X-Accel-Buffering"] = "no"
    return response
