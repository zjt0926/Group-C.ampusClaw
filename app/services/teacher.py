from datetime import datetime

from ..audit import record_skill
from ..extensions import db
from ..models import Submission, WrongQuestion


class TeacherActionError(Exception):
    def __init__(self, message, error_code="bad_request"):
        super().__init__(message)
        self.message = message
        self.error_code = error_code


def override_score(user, submission, score, comment):
    if submission.status != "graded":
        raise TeacherActionError("该提交尚未完成 AI 批改", "not_graded")
    old_score = submission.teacher_score
    old_comment = submission.teacher_comment
    submission.teacher_score = score
    submission.teacher_comment = comment
    db.session.commit()
    record_skill(
        user,
        None,
        "grade_override",
        "success",
        0,
        None,
        {
            "submission_id": submission.id,
            "old_score": old_score,
            "new_score": score,
            "old_comment": old_comment,
            "new_comment": comment,
        },
    )


def mark_wrong(user, submission):
    if submission.status != "graded":
        raise TeacherActionError("该提交尚未完成 AI 批改", "not_graded")
    existing = WrongQuestion.query.filter_by(submission_id=submission.id, question_no=1).first()
    if existing is None:
        wrong = WrongQuestion(
            submission_id=submission.id,
            student_id=submission.student_id,
            class_id=submission.class_id,
            subject=submission.assignment.subject,
            question_no=1,
            question_text=f"{submission.assignment.title}\n{submission.assignment.description}".strip(),
            my_answer=submission.content,
            error_reason="教师判定：该题判错。",
        )
        db.session.add(wrong)
    else:
        existing.error_reason = "教师判定：该题判错。"
    submission.is_wrong = True
    db.session.commit()
    record_skill(
        user,
        None,
        "mark_wrong",
        "success",
        0,
        None,
        {"submission_id": submission.id},
    )


def undo_mark_wrong(user, submission):
    WrongQuestion.query.filter_by(submission_id=submission.id).delete()
    submission.is_wrong = False
    db.session.commit()
    record_skill(
        user,
        None,
        "undo_mark_wrong",
        "success",
        0,
        None,
        {"submission_id": submission.id},
    )
