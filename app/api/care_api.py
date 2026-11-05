from flask import Blueprint, g, jsonify, request

from ..auth import json_error, role_required
from ..services.care import HELP_CHANNELS, CareError, handle_message, history
from ..services.skills import skill_enabled

bp = Blueprint("care_api", __name__, url_prefix="/api/care")


@bp.get("/history")
@role_required("student")
def care_history():
    if not skill_enabled(g.current_user.class_id, "care_chat"):
        return (
            jsonify(
                {
                    "error": "该能力已被教师关闭",
                    "error_code": "skill_disabled",
                    "help_channels": HELP_CHANNELS,
                }
            ),
            409,
        )
    return jsonify({"items": history(g.current_user.class_id, g.current_user.id), "help_channels": HELP_CHANNELS})


@bp.post("/chat")
@role_required("student")
def care_chat():
    if not skill_enabled(g.current_user.class_id, "care_chat"):
        return (
            jsonify(
                {
                    "error": "该能力已被教师关闭",
                    "error_code": "skill_disabled",
                    "help_channels": HELP_CHANNELS,
                }
            ),
            409,
        )
    payload = request.get_json(silent=True) or {}
    message = str(payload.get("message", "")).strip()
    if not message or len(message) > 1000:
        return json_error("消息必须为 1—1000 字符", 400, "invalid_message")
    try:
        reply, risk, mode = handle_message(g.current_user, message)
    except CareError as exc:
        return json_error(exc.message, 400, exc.error_code)
    return jsonify(
        {
            "reply": reply,
            "risk": risk,
            "mode": mode,
            "help_channels": HELP_CHANNELS,
        }
    )
