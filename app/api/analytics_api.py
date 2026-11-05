from flask import Blueprint, g, jsonify

from ..auth import json_error, role_required
from ..services.analytics import aggregate

bp = Blueprint("analytics_api", __name__, url_prefix="/api")


@bp.get("/analytics/me")
@role_required("student")
def analytics_me():
    try:
        data = aggregate(g.current_user)
    except Exception:  # noqa: BLE001
        return json_error("学情数据暂时不可用，请稍后重试", 503, "analytics_unavailable")
    return jsonify(data)
