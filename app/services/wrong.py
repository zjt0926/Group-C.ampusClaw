import json
import time
from datetime import datetime

from ..adapters import ai_gateway
from ..audit import record_skill
from ..extensions import db
from ..models import WrongQuestion
from ..retrieval import search_chunks


class WrongQuestionError(Exception):
    def __init__(self, message, error_code="bad_request"):
        super().__init__(message)
        self.message = message
        self.error_code = error_code


def list_wrong_questions(class_id, student_id, subject):
    query = WrongQuestion.query.filter_by(
        class_id=class_id, student_id=student_id, subject=subject
    )
    return [item.to_dict() for item in query.order_by(WrongQuestion.created_at.desc()).all()]


def _claim(wrong_id):
    return (
        db.session.query(WrongQuestion)
        .filter(WrongQuestion.id == wrong_id, WrongQuestion.explained_at.is_(None))
        .update({"explained_at": datetime.utcnow()}, synchronize_session=False)
    )


def explain(user, wrong_id):
    wrong = WrongQuestion.query.filter_by(
        id=wrong_id, class_id=user.class_id, student_id=user.id
    ).first()
    if wrong is None:
        raise WrongQuestionError("错题不存在", "not_found")

    if wrong.explanation:
        return json.loads(wrong.explanation), True

    claimed = _claim(wrong.id)
    db.session.commit()
    if not claimed:
        # 另一个请求正在生成，最多等 2 秒后读取缓存结果
        for _ in range(4):
            time.sleep(0.5)
            db.session.expire_all()
            current = db.session.get(WrongQuestion, wrong.id)
            if current and current.explanation:
                return json.loads(current.explanation), True
        raise WrongQuestionError("讲解正在生成，请稍后再试", "explaining")

    started = datetime.utcnow()
    hits = search_chunks(wrong.class_id, wrong.subject, wrong.question_text + " " + wrong.error_reason)
    try:
        result = ai_gateway.explain_wrong_question(wrong, hits)
    except Exception as exc:  # noqa: BLE001
        wrong.explained_at = None
        db.session.commit()
        record_skill(
            user,
            "wrong_explain",
            "explain",
            "timeout" if isinstance(exc, ai_gateway.AIGatewayTimeout) else "error",
            (datetime.utcnow() - started).total_seconds() * 1000,
            None,
            {"wrong_question_id": wrong.id},
        )
        raise WrongQuestionError(f"讲解生成失败：{exc}", "explain_failed") from exc

    payload = {
        "error_analysis": result["error_analysis"],
        "knowledge_points": result["knowledge_points"],
        "advice": result["advice"],
        "no_hit": result.get("no_hit", False),
    }
    wrong.explanation = json.dumps(payload, ensure_ascii=False)
    wrong.explained_at = datetime.utcnow()
    db.session.commit()

    record_skill(
        user,
        "wrong_explain",
        "explain",
        "success",
        (datetime.utcnow() - started).total_seconds() * 1000,
        result.get("tokens"),
        {"wrong_question_id": wrong.id},
    )
    return payload, False
