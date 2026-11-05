from flask import Blueprint, g, jsonify, request

from ..auth import json_error, role_required, valid_subject
from ..models import SUBJECTS
from ..services.skills import skill_enabled
from ..services.wrong import WrongQuestionError, explain, list_wrong_questions

bp = Blueprint("wrong_api", __name__, url_prefix="/api")


@bp.get("/wrong-questions")
@role_required("student")
def wrong_questions():
    subject = request.args.get("subject", SUBJECTS[0])
    if not valid_subject(subject):
        return json_error("学科参数不合法", 400, "invalid_subject")
    items = list_wrong_questions(g.current_user.class_id, g.current_user.id, subject)
    return jsonify({"items": items, "total": len(items), "subject": subject})


@bp.post("/wrong-questions/<int:wrong_id>/explain")
@role_required("student")
def explain_wrong(wrong_id):
    if not skill_enabled(g.current_user.class_id, "wrong_explain"):
        return json_error("错题讲解技能已被教师停用", 409, "skill_disabled")
    try:
        payload, cached = explain(g.current_user, wrong_id)
    except WrongQuestionError as exc:
        if exc.error_code == "not_found":
            return json_error(exc.message, 404, "not_found")
        if exc.error_code == "explaining":
            return json_error(exc.message, 409, "explaining")
        return json_error(exc.message, 500, "explain_failed")
    return jsonify({"explanation": payload, "cached": cached})
