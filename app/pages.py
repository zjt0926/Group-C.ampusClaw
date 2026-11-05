from flask import Blueprint, g, redirect, render_template, request, make_response

from .auth import login_required, role_required

bp = Blueprint("pages", __name__)


def _home_for(user):
    return "/teacher" if user.role == "teacher" else "/student"


@bp.get("/login")
def login():
    user = getattr(g, "current_user", None)
    if user is not None and user.class_id:
        return redirect(_home_for(user))
    return render_template("login.html", next_path=request.args.get("next", ""))


@bp.get("/logout")
def logout():
    target = request.args.get("next") or "/login"
    response = make_response(redirect(target))
    response.delete_cookie("access_token")
    return response


@bp.get("/")
@login_required
def index():
    return redirect(_home_for(g.current_user))


@bp.get("/teacher")
@role_required("teacher")
def teacher_dashboard():
    return render_template("teacher_dashboard.html", page_id="teacher-dashboard")


@bp.get("/teacher/lectures")
@role_required("teacher")
def teacher_lectures():
    return render_template("teacher_lectures.html", page_id="teacher-lectures")


@bp.get("/teacher/assistant")
@role_required("teacher")
def teacher_assistant():
    return render_template("teacher_assistant.html", page_id="teacher-assistant")


@bp.get("/teacher/homework")
@role_required("teacher")
def teacher_homework():
    return render_template("teacher_homework.html", page_id="teacher-homework")


@bp.get("/teacher/audit")
@role_required("teacher")
def teacher_audit():
    return render_template("teacher_audit.html", page_id="teacher-audit")


@bp.get("/student")
@role_required("student")
def student_dashboard():
    return render_template("student_dashboard.html", page_id="student-dashboard")


@bp.get("/student/knowledge")
@role_required("student")
def student_knowledge():
    return render_template("student_knowledge.html", page_id="student-knowledge")


@bp.get("/student/chat")
@role_required("student")
def student_chat():
    return render_template("student_chat.html", page_id="student-chat")


@bp.get("/student/submit")
@role_required("student")
def student_submit():
    return render_template("student_submit.html", page_id="student-submit")


@bp.get("/student/mistakes")
@role_required("student")
def student_mistakes():
    return render_template("student_mistakes.html", page_id="student-mistakes")


@bp.get("/student/care")
@role_required("student")
def student_care():
    return render_template("student_care.html", page_id="student-care")


@bp.get("/student/analytics")
@role_required("student")
def student_analytics():
    return render_template("student_analytics.html", page_id="student-analytics")
