import functools
from datetime import datetime, timedelta, timezone

import jwt
from flask import current_app, g, jsonify, redirect, request, url_for

from .extensions import db
from .models import SUBJECTS, User


def create_access_token(user):
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user.id,
        "role": user.role,
        "class_id": user.class_id,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=current_app.config["JWT_MAX_AGE"])).timestamp()),
    }
    return jwt.encode(payload, current_app.config["JWT_SECRET"], algorithm="HS256")


def decode_token(token):
    if not token:
        return None
    try:
        return jwt.decode(token, current_app.config["JWT_SECRET"], algorithms=["HS256"])
    except jwt.PyJWTError:
        return None


def load_current_user():
    token = request.cookies.get("access_token")
    if not token:
        header = request.headers.get("Authorization", "")
        if header.startswith("Bearer "):
            token = header[7:].strip()
    payload = decode_token(token)
    if not payload:
        return None
    user = db.session.get(User, payload.get("sub"))
    return user


def is_api_request():
    return request.path.startswith("/api/")


def json_error(message, status, error_code=None):
    body = {"error": message}
    if error_code:
        body["error_code"] = error_code
    return jsonify(body), status


def login_required(view):
    @functools.wraps(view)
    def wrapper(*args, **kwargs):
        user = getattr(g, "current_user", None)
        if user is None:
            if is_api_request():
                return json_error("未登录或登录已失效", 401, "unauthorized")
            return redirect(url_for("pages.login", next=request.path))
        if not user.class_id:
            if is_api_request():
                return json_error("账号未分配班级", 403, "no_class")
            return redirect(url_for("pages.login"))
        return view(*args, **kwargs)

    return wrapper


def role_required(*roles):
    def decorator(view):
        @functools.wraps(view)
        def wrapper(*args, **kwargs):
            user = getattr(g, "current_user", None)
            if user is None:
                if is_api_request():
                    return json_error("未登录或登录已失效", 401, "unauthorized")
                return redirect(url_for("pages.login", next=request.path))
            if user.role not in roles:
                if is_api_request():
                    return json_error("无权限访问该资源", 403, "forbidden")
                target = "pages.teacher_dashboard" if user.role == "teacher" else "pages.student_dashboard"
                return redirect(url_for(target))
            if not user.class_id:
                if is_api_request():
                    return json_error("账号未分配班级", 403, "no_class")
                return redirect(url_for("pages.login"))
            return view(*args, **kwargs)

        return wrapper

    return decorator


def valid_subject(subject):
    return subject in SUBJECTS


def class_id_of(user):
    """班级只来自登录会话，请求参数中的 class_id 一律忽略。"""
    return user.class_id
