import json
import os
import time
from datetime import datetime

from flask import Blueprint, Response, g, jsonify, request, stream_with_context
from sqlalchemy import case, func

from ..auth import json_error, login_required, role_required, valid_subject
from ..extensions import db
from ..models import Assignment, Submission, SUBJECTS
from ..services.submissions import SubmissionError, create_submission, list_student_assignments

bp = Blueprint("assignments_api", __name__, url_prefix="/api")


def _enqueue(submission_id):
    """入队失败时回滚 pending 孤儿行，返回 False 让接口返回 503。"""
    if os.getenv("CELERY_ALWAYS_EAGER") == "1":
        from ..services.submissions import run_grading

        run_grading(submission_id)
        return True
    try:
        from ..tasks import grade_submission_task

        grade_submission_task.delay(submission_id)
        return True
    except Exception:  # noqa: BLE001
        return False


def _accessible_submission(user, submission_id):
    query = Submission.query.filter_by(id=submission_id, class_id=user.class_id)
    if user.role != "teacher":
        query = query.filter_by(student_id=user.id)
    return query.first()


@bp.get("/assignments")
@login_required
def assignments():
    subject = request.args.get("subject", SUBJECTS[0])
    if not valid_subject(subject):
        return json_error("学科参数不合法", 400, "invalid_subject")
    if g.current_user.role != "student":
        return json_error("该接口仅学生可用", 403, "forbidden")
    items = list_student_assignments(g.current_user.class_id, subject, g.current_user.id)
    return jsonify({"items": items, "total": len(items), "subject": subject})


@bp.post("/assignments")
@role_required("teacher")
def create_assignment():
    payload = request.get_json(silent=True) or {}
    subject = payload.get("subject")
    title = str(payload.get("title", "")).strip()
    description = str(payload.get("description", "")).strip()
    deadline_raw = str(payload.get("deadline", "")).strip()
    if not valid_subject(subject):
        return json_error("学科参数不合法", 400, "invalid_subject")
    if not title or len(title) > 200:
        return json_error("作业标题必须为 1—200 字符", 400, "invalid_title")
    try:
        deadline = datetime.fromisoformat(deadline_raw.replace("Z", ""))
    except ValueError:
        return json_error("截止时间格式不合法", 400, "invalid_deadline")
    assignment = Assignment(
        class_id=g.current_user.class_id,
        subject=subject,
        title=title,
        description=description,
        deadline=deadline,
        created_by=g.current_user.id,
    )
    db.session.add(assignment)
    db.session.commit()
    return jsonify({"assignment": assignment.to_dict()}), 201


@bp.post("/assignments/<int:assignment_id>/submit")
@role_required("student")
def submit(assignment_id):
    assignment = Assignment.query.filter_by(
        id=assignment_id, class_id=g.current_user.class_id
    ).first()
    if assignment is None:
        return json_error("作业不存在", 404, "not_found")

    if datetime.utcnow() >= assignment.deadline:
        return json_error("已过截止时间，无法提交", 409, "assignment_closed")

    payload = request.get_json(silent=True) or {}
    content = str(payload.get("content", "")).strip()
    idempotency_key = str(payload.get("idempotency_key", "")).strip()
    if not idempotency_key or len(idempotency_key) > 80:
        return json_error("缺少有效的 idempotency_key", 400, "invalid_key")
    if not content or len(content) > 5000:
        return json_error("作答内容必须为 1—5000 字符", 400, "invalid_content")

    submission, duplicated = create_submission(g.current_user, assignment, content, idempotency_key)
    if duplicated:
        return jsonify({"submission_id": submission.id, "status": submission.status}), 200

    if not _enqueue(submission.id):
        db.session.delete(submission)
        db.session.commit()
        return json_error("批改队列暂不可用，请稍后重试", 503, "queue_unavailable")

    return jsonify({"submission_id": submission.id, "status": submission.status}), 202


@bp.get("/submissions")
@role_required("student")
def submissions():
    subject = request.args.get("subject", SUBJECTS[0])
    if not valid_subject(subject):
        return json_error("学科参数不合法", 400, "invalid_subject")
    items = (
        Submission.query.join(Assignment, Submission.assignment_id == Assignment.id)
        .filter(
            Submission.class_id == g.current_user.class_id,
            Submission.student_id == g.current_user.id,
            Assignment.subject == subject,
        )
        .order_by(Submission.created_at.desc())
        .all()
    )
    return jsonify({"items": [item.to_dict() for item in items], "total": len(items)})


@bp.get("/submissions/<int:submission_id>")
@login_required
def submission_detail(submission_id):
    submission = _accessible_submission(g.current_user, submission_id)
    if submission is None:
        return json_error("提交不存在", 404, "not_found")
    return jsonify({"submission": submission.to_dict()})


@bp.get("/submissions/<int:submission_id>/stream")
@login_required
def submission_stream(submission_id):
    submission = _accessible_submission(g.current_user, submission_id)
    if submission is None:
        return json_error("提交不存在", 404, "not_found")

    def generate():
        started = time.time()
        last_status = None
        heartbeat = 0
        yield "retry: 2000\n\n"
        while True:
            db.session.expire_all()
            current = _accessible_submission(g.current_user, submission_id)
            if current is None:
                yield "event: error\ndata: {}\n\n"
                break
            payload = current.to_dict()
            if payload["status"] != last_status:
                last_status = payload["status"]
                heartbeat = 0
                yield f"event: status\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
            if payload["status"] in {"graded", "failed"}:
                break
            heartbeat += 1
            if heartbeat >= 12:
                heartbeat = 0
                yield ": keep-alive\n\n"
            if time.time() - started > 120:
                break
            time.sleep(2)

    response = Response(stream_with_context(generate()), mimetype="text/event-stream")
    response.headers["Cache-Control"] = "no-cache"
    response.headers["X-Accel-Buffering"] = "no"
    return response


@bp.post("/submissions/<int:submission_id>/retry")
@role_required("student")
def retry_submission(submission_id):
    submission = _accessible_submission(g.current_user, submission_id)
    if submission is None:
        return json_error("提交不存在", 404, "not_found")
    if submission.status != "failed":
        return json_error("只有失败的提交可以重试", 409, "not_retryable")
    submission.status = "pending"
    submission.error_message = None
    db.session.commit()
    if not _enqueue(submission.id):
        submission.status = "failed"
        submission.error_message = "批改队列暂不可用"
        db.session.commit()
        return json_error("批改队列暂不可用，请稍后重试", 503, "queue_unavailable")
    return jsonify({"submission_id": submission.id, "status": "pending"}), 202


@bp.post("/teacher/submissions/<int:submission_id>/retry")
@role_required("teacher")
def teacher_retry_submission(submission_id):
    submission = Submission.query.filter_by(
        id=submission_id, class_id=g.current_user.class_id
    ).first()
    if submission is None:
        return json_error("提交不存在", 404, "not_found")
    if submission.status != "failed":
        return json_error("只有失败的提交可以重试", 409, "not_retryable")
    submission.status = "pending"
    submission.error_message = None
    db.session.commit()
    if not _enqueue(submission.id):
        submission.status = "failed"
        submission.error_message = "批改队列暂不可用"
        db.session.commit()
        return json_error("批改队列暂不可用，请稍后重试", 503, "queue_unavailable")
    return jsonify({"submission_id": submission.id, "status": "pending"}), 202


@bp.get("/teacher/submissions")
@role_required("teacher")
def teacher_submissions():
    subject = request.args.get("subject", SUBJECTS[0])
    if not valid_subject(subject):
        return json_error("学科参数不合法", 400, "invalid_subject")
    query = (
        Submission.query.join(Assignment, Submission.assignment_id == Assignment.id)
        .filter(Submission.class_id == g.current_user.class_id)
        .filter(Assignment.subject == subject)
    )
    items = query.order_by(Submission.created_at.desc()).all()
    return jsonify({"items": [item.to_dict() for item in items], "total": len(items)})


@bp.patch("/submissions/<int:submission_id>/score")
@role_required("teacher")
def override_score(submission_id):
    from ..services.teacher import TeacherActionError, override_score as apply_score

    submission = Submission.query.filter_by(
        id=submission_id, class_id=g.current_user.class_id
    ).first()
    if submission is None:
        return json_error("提交不存在", 404, "not_found")
    payload = request.get_json(silent=True) or {}
    score = payload.get("teacher_score")
    comment = payload.get("teacher_comment", "")
    if not isinstance(score, int) or isinstance(score, bool) or not 0 <= score <= 100:
        return json_error("终评分数必须为 0—100 的整数", 400, "invalid_score")
    if not isinstance(comment, str) or len(comment) > 500:
        return json_error("终评评语不能超过 500 字符", 400, "invalid_comment")
    try:
        apply_score(g.current_user, submission, score, comment)
    except TeacherActionError as exc:
        return json_error(exc.message, 409, exc.error_code)
    return jsonify({"submission": submission.to_dict()})


@bp.post("/submissions/<int:submission_id>/mark-wrong")
@role_required("teacher")
def mark_wrong(submission_id):
    from ..services.teacher import TeacherActionError, mark_wrong as apply_mark

    submission = Submission.query.filter_by(
        id=submission_id, class_id=g.current_user.class_id
    ).first()
    if submission is None:
        return json_error("提交不存在", 404, "not_found")
    try:
        apply_mark(g.current_user, submission)
    except TeacherActionError as exc:
        return json_error(exc.message, 409, exc.error_code)
    return jsonify({"submission": submission.to_dict()})


@bp.delete("/submissions/<int:submission_id>/mark-wrong")
@role_required("teacher")
def undo_mark_wrong(submission_id):
    from ..services.teacher import undo_mark_wrong as undo

    submission = Submission.query.filter_by(
        id=submission_id, class_id=g.current_user.class_id
    ).first()
    if submission is None:
        return json_error("提交不存在", 404, "not_found")
    undo(g.current_user, submission)
    return jsonify({"submission": submission.to_dict()})
