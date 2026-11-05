from datetime import datetime

from flask import Blueprint, g, jsonify

from ..auth import role_required
from ..models import (
    SUBJECTS,
    Assignment,
    AuditLog,
    ChatMessage,
    Submission,
    User,
    WrongQuestion,
)

bp = Blueprint("dashboard_api", __name__, url_prefix="/api")


@bp.get("/student/dashboard")
@role_required("student")
def student_dashboard():
    user = g.current_user
    now = datetime.utcnow()
    assignments = (
        Assignment.query.filter_by(class_id=user.class_id)
        .filter(Assignment.deadline > now)
        .order_by(Assignment.deadline.asc())
        .limit(6)
        .all()
    )
    items = []
    for assignment in assignments:
        submission = (
            Submission.query.filter_by(
                assignment_id=assignment.id, student_id=user.id, class_id=user.class_id
            )
            .order_by(Submission.created_at.desc())
            .first()
        )
        item = assignment.to_dict()
        item["submission_status"] = submission.status if submission else "unsubmitted"
        items.append(item)

    graded = Submission.query.filter_by(
        class_id=user.class_id, student_id=user.id, status="graded"
    ).count()
    wrong = WrongQuestion.query.filter_by(class_id=user.class_id, student_id=user.id).count()
    questions = ChatMessage.query.filter_by(
        class_id=user.class_id, student_id=user.id, role="user"
    ).count()
    return jsonify(
        {
            "upcoming": items,
            "stats": {
                "unsubmitted": sum(1 for item in items if item["submission_status"] == "unsubmitted"),
                "graded": graded,
                "wrong": wrong,
                "questions": questions,
            },
        }
    )


@bp.get("/teacher/dashboard")
@role_required("teacher")
def teacher_dashboard():
    user = g.current_user
    class_id = user.class_id
    students = User.query.filter_by(class_id=class_id, role="student").count()
    assignments = Assignment.query.filter_by(class_id=class_id).count()
    submissions = Submission.query.filter_by(class_id=class_id).all()
    pending = sum(1 for item in submissions if item.status in {"pending", "grading"})
    graded = [item for item in submissions if item.status == "graded"]
    mastery = {}
    for subject in SUBJECTS:
        values = []
        for item in graded:
            if item.assignment and item.assignment.subject == subject:
                value = item.teacher_score if item.teacher_score is not None else item.ai_score
                if value is not None:
                    values.append(value)
        mastery[subject] = round(sum(values) / len(values), 1) if values else None
    skill_calls = AuditLog.query.filter(
        AuditLog.class_id == class_id, AuditLog.skill.isnot(None)
    ).count()
    recent = sorted(graded, key=lambda item: item.graded_at or item.created_at, reverse=True)[:5]
    return jsonify(
        {
            "stats": {
                "students": students,
                "assignments": assignments,
                "submissions": len(submissions),
                "pending": pending,
                "skill_calls": skill_calls,
                "mastery": mastery,
            },
            "recent": [item.to_dict() for item in recent],
        }
    )
