from datetime import datetime

from flask import Blueprint, g, jsonify, request

from ..auth import json_error, role_required
from ..services.audit_service import list_logs, overall, summary

bp = Blueprint("audit_api", __name__, url_prefix="/api/teacher")


@bp.get("/audit/summary")
@role_required("teacher")
def audit_summary():
    return jsonify(
        {
            "overall": overall(g.current_user.class_id),
            "skills": summary(g.current_user.class_id),
        }
    )


@bp.get("/audit")
@role_required("teacher")
def audit_logs():
    skill = request.args.get("skill") or None
    status = request.args.get("status") or None
    start_raw = request.args.get("start")
    end_raw = request.args.get("end")
    try:
        start = datetime.fromisoformat(start_raw) if start_raw else None
        end = datetime.fromisoformat(end_raw) if end_raw else None
    except ValueError:
        return json_error("时间格式不合法", 400, "invalid_time")
    page = request.args.get("page", 1)
    page_size = request.args.get("page_size", 20)
    try:
        page = int(page)
        page_size = int(page_size)
    except ValueError:
        return json_error("分页参数不合法", 400, "invalid_pagination")
    data = list_logs(g.current_user.class_id, skill, status, start, end, page, page_size)
    return jsonify(data)
