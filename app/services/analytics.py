from collections import defaultdict
from datetime import datetime, timedelta

from ..adapters import ai_gateway
from ..audit import record_skill
from ..extensions import db
from ..models import SUBJECTS, ChatMessage, Submission, WrongQuestion


def _score_of(submission):
    return submission.teacher_score if submission.teacher_score is not None else submission.ai_score


def _week_key(moment):
    iso = moment.isocalendar()
    return f"{iso[0]}-W{iso[1]:02d}"


def aggregate(user):
    base = {"class_id": user.class_id, "student_id": user.id}

    question_count = ChatMessage.query.filter_by(role="user", **base).count()
    submissions = Submission.query.filter_by(**base).order_by(Submission.created_at.asc()).all()
    graded = [item for item in submissions if item.status == "graded"]
    wrong_count = WrongQuestion.query.filter_by(**base).count()

    correct_count = sum(1 for item in graded if (item.ai_score or 0) >= 60)
    correct_rate = (correct_count / len(graded)) if graded else None

    mastery = {}
    for subject in SUBJECTS:
        values = [
            _score_of(item)
            for item in graded
            if item.assignment and item.assignment.subject == subject and _score_of(item) is not None
        ]
        mastery[subject] = round(sum(values) / len(values), 1) if values else None

    trend = []
    for item in graded[-10:]:
        trend.append(
            {
                "submission_id": item.id,
                "subject": item.assignment.subject if item.assignment else "",
                "score": _score_of(item),
                "date": (item.graded_at or item.created_at).isoformat() + "Z",
            }
        )

    week_starts = []
    now = datetime.utcnow()
    for index in range(3, -1, -1):
        week_starts.append(now - timedelta(days=7 * index))
    weeks = [moment.strftime("%m-%d") for moment in week_starts]
    heat_matrix = {subject: [0 for _ in week_starts] for subject in SUBJECTS}
    for item in submissions:
        moment = item.created_at
        subject = item.assignment.subject if item.assignment else None
        if subject not in heat_matrix:
            continue
        for index, week_start in enumerate(week_starts):
            if index == len(week_starts) - 1 or moment < week_starts[index + 1]:
                if moment >= week_start - timedelta(days=7):
                    heat_matrix[subject][index] += 1
                    break

    profile = None
    profile_note = None
    profile_error = False
    if len(graded) >= 3:
        weak_topics = []
        for wrong in (
            WrongQuestion.query.filter_by(**base).order_by(WrongQuestion.created_at.desc()).limit(5)
        ):
            weak_topics.append(f"{wrong.subject}：{wrong.error_reason[:24]}")
        stats = {
            "questions": question_count,
            "submissions": len(submissions),
            "correct_rate": correct_rate,
            "wrong_questions": wrong_count,
            "mastery": mastery,
        }
        started = datetime.utcnow()
        try:
            profile = ai_gateway.learning_profile(stats, weak_topics)
            record_skill(
                user,
                "learning_profile",
                "profile",
                "success",
                (datetime.utcnow() - started).total_seconds() * 1000,
                profile.get("tokens"),
                {"graded": len(graded)},
            )
        except Exception as exc:  # noqa: BLE001
            profile = None
            profile_error = True
            record_skill(
                user,
                "learning_profile",
                "profile",
                "timeout" if isinstance(exc, ai_gateway.AIGatewayTimeout) else "error",
                (datetime.utcnow() - started).total_seconds() * 1000,
                None,
                {"graded": len(graded)},
            )
    else:
        profile_note = "数据不足，暂不生成画像"

    return {
        "metrics": {
            "questions": question_count,
            "submissions": len(submissions),
            "correct_rate": correct_rate,
            "wrong_questions": wrong_count,
        },
        "mastery": mastery,
        "trend": trend,
        "heat": {
            "weeks": [f"第{index + 1}周" for index in range(len(weeks))],
            "matrix": heat_matrix,
        },
        "profile": profile,
        "profile_note": profile_note,
        "profile_error": profile_error,
        "graded_count": len(graded),
        "mode": "gateway" if ai_gateway.is_configured() else "local-demo",
    }
