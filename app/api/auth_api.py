from datetime import datetime

from flask import Blueprint, current_app, g, jsonify, make_response, request
from werkzeug.security import check_password_hash

from ..auth import create_access_token, json_error, login_required
from ..extensions import db
from ..models import User

bp = Blueprint("auth_api", __name__, url_prefix="/api/auth")


@bp.post("/login")
def login():
    payload = request.get_json(silent=True) or {}
    username = str(payload.get("username", "")).strip()
    password = str(payload.get("password", ""))
    if not username or not password:
        return json_error("请输入账号和密码", 400, "invalid_credentials")

    user = User.query.filter_by(username=username).first()
    if user is None or not check_password_hash(user.password_hash, password):
        return json_error("账号或密码错误", 401, "invalid_credentials")
    if not user.class_id:
        return json_error("账号未分配班级", 403, "no_class")

    token = create_access_token(user)
    response = make_response(jsonify({"user": user.to_public_dict()}))
    response.set_cookie(
        "access_token",
        token,
        max_age=current_app.config["JWT_MAX_AGE"],
        httponly=True,
        samesite="Lax",
        secure=current_app.config["COOKIE_SECURE"],
    )
    return response


@bp.post("/logout")
def logout():
    response = make_response(jsonify({"ok": True}))
    response.delete_cookie("access_token")
    return response


@bp.get("/me")
@login_required
def me():
    return jsonify({"user": g.current_user.to_public_dict()})
