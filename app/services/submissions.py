import json
from datetime import datetime

from flask import current_app

from ..adapters import ai_gateway
from ..audit import record_skill
from ..extensions import db
from ..models import Assignment, Submission, User, WrongQuestion
from ..retrieval import search_chunks


class SubmissionError(Exception):
    def __init__(self, message, error_code="bad_request"):
        super().__init__(message)
        self.message = message
        self.error_code = error_code


def list_student_assignments(class_id, subject, student_id):
    now = datetime.utcnow()
    assignments = (
        Assignment.query.filter_by(class_id=class_id, subject=subject)
        .order_by(Assignment.deadline.asc())
        .all()
    )
    result = []
    for assignment in assignments:
        submission = (
            Submission.query.filter_by(
                assignment_id=assignment.id, student_id=student_id, class_id=class_id
            )
            .order_by(Submission.created_at.desc())
            .first()
        )
        item = assignment.to_dict()
        item["closed"] = assignment.deadline <= now
        item["submission"] = submission.to_dict() if submission else None
        result.append(item)
    return result


def create_submission(user, assignment, content, idempotency_key):
    existing = Submission.query.filter_by(
        assignment_id=assignment.id, student_id=user.id, idempotency_key=idempotency_key
    ).first()
    if existing:
        return existing, True

    submission = Submission(
        assignment_id=assignment.id,
        student_id=user.id,
        class_id=user.class_id,
        content=content,
        idempotency_key=idempotency_key,
        status="pending",
    )
    db.session.add(submission)
    try:
        db.session.commit()
    except Exception as exc:  # 唯一约束竞态：回读已存在行
        db.session.rollback()
        existing = Submission.query.filter_by(
            assignment_id=assignment.id, student_id=user.id, idempotency_key=idempotency_key
        ).first()
        if existing:
            return existing, True
        raise SubmissionError("提交写入失败") from exc
    return submission, False


def _mark_failed(submission, message):
    submission.status = "failed"
    submission.error_message = message[:500]
    submission.ai_score = None
    submission.ai_comment = None
    db.session.commit()


def _ensure_wrong_question(submission, result):
    assignment = submission.assignment
    question_text = f"{assignment.title}\n{assignment.description}".strip()
    existing = WrongQuestion.query.filter_by(
        submission_id=submission.id, question_no=1
    ).first()
    if existing:
        existing.error_reason = result["comment"]
        return existing
    wrong = WrongQuestion(
        submission_id=submission.id,
        student_id=submission.student_id,
        class_id=submission.class_id,
        subject=assignment.subject,
        question_no=1,
        question_text=question_text,
        my_answer=submission.content,
        error_reason=result["comment"],
    )
    db.session.add(wrong)
    try:
        db.session.flush()
    except Exception:  # 并发重复，回读已有记录
        db.session.rollback()
        return WrongQuestion.query.filter_by(submission_id=submission.id, question_no=1).first()
    return wrong


def run_grading(submission_id):
    """worker 内执行。返回 True 表示本次真正完成一次批改。"""
    submission = db.session.get(Submission, submission_id)
    if submission is None:
        return False

    # 条件更新抢占：只有 pending 才能进入 grading，重复投递直接返回
    updated = (
        db.session.query(Submission)
        .filter(Submission.id == submission_id, Submission.status == "pending")
        .update({"status": "grading"}, synchronize_session=False)
    )
    db.session.commit()
    if not updated:
        return False

    submission = db.session.get(Submission, submission_id)
    assignment = submission.assignment
    started = datetime.utcnow()
    hits = search_chunks(submission.class_id, assignment.subject, assignment.title + " " + assignment.description)

    try:
        result = ai_gateway.grade_submission(assignment, submission.content, hits)
    except ai_gateway.AIGatewayTimeout as exc:
        _mark_failed(submission, f"批改超时：{exc}")
        record_skill(
            submission.student,
            "homework_grade",
            "grade",
            "timeout",
            (datetime.utcnow() - started).total_seconds() * 1000,
            None,
            {"submission_id": submission.id},
        )
        return False
    except Exception as exc:  # noqa: BLE001
        _mark_failed(submission, f"批改失败：{exc}")
        record_skill(
            submission.student,
            "homework_grade",
            "grade",
            "error",
            (datetime.utcnow() - started).total_seconds() * 1000,
            None,
            {"submission_id": submission.id},
        )
        return False

    # 先写 AI 结果，再按判错规则补错题；任一步失败都不会写入非法分数
    submission.ai_score = result["score"]
    submission.ai_comment = result["comment"]
    submission.ai_evidence = json.dumps(result["evidence"], ensure_ascii=False)
    submission.status = "graded"
    submission.graded_at = datetime.utcnow()
    submission.error_message = None

    is_wrong = bool(result.get("is_wrong")) or result["score"] < current_app.config["PASS_SCORE"]
    submission.is_wrong = is_wrong
    if is_wrong:
        _ensure_wrong_question(submission, result)

    db.session.commit()

    record_skill(
        submission.student,
        "homework_grade",
        "grade",
        "success",
        (datetime.utcnow() - started).total_seconds() * 1000,
        result.get("tokens"),
        {"submission_id": submission.id, "score": result["score"]},
    )
    return True
