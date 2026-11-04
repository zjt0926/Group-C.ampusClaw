import logging
import time
from datetime import datetime

from flask import Flask, g, jsonify, render_template, request

from .audit import audit_failure_count, record_api
from .auth import load_current_user
from .config import Config
from .extensions import db
from .models import SUBJECTS, SUBJECT_ICONS

NAV_ITEMS = {
    "teacher": [
        {"endpoint": "pages.teacher_dashboard", "label": "本班首页", "icon": "🏫", "path": "/teacher"},
        {"endpoint": "pages.teacher_lectures", "label": "讲义管理", "icon": "📚", "path": "/teacher/lectures"},
        {"endpoint": "pages.teacher_assistant", "label": "助手配置", "icon": "🛠️", "path": "/teacher/assistant"},
        {"endpoint": "pages.teacher_homework", "label": "作业与改分", "icon": "📝", "path": "/teacher/homework"},
        {"endpoint": "pages.teacher_audit", "label": "审计与统计", "icon": "📊", "path": "/teacher/audit"},
    ],
    "student": [
        {"endpoint": "pages.student_dashboard", "label": "本班首页", "icon": "🏫", "path": "/student"},
        {"endpoint": "pages.student_knowledge", "label": "讲义与检索", "icon": "🔍", "path": "/student/knowledge"},
        {"endpoint": "pages.student_chat", "label": "助手对话", "icon": "💬", "path": "/student/chat"},
        {"endpoint": "pages.student_submit", "label": "交作业", "icon": "✍️", "path": "/student/submit"},
        {"endpoint": "pages.student_mistakes", "label": "错题", "icon": "📕", "path": "/student/mistakes"},
        {"endpoint": "pages.student_care", "label": "关怀式对话", "icon": "🤗", "path": "/student/care"},
        {"endpoint": "pages.student_analytics", "label": "学情分析", "icon": "📈", "path": "/student/analytics"},
    ],
}


def create_app(config_object=Config):
    app = Flask(__name__)
    app.config.from_object(config_object)
    app.json.ensure_ascii = False
    logging.basicConfig(level=logging.INFO)
    db.init_app(app)

    from .api.analytics_api import bp as analytics_bp
    from .api.assistant_api import bp as assistant_bp
    from .api.assignments_api import bp as assignments_bp
    from .api.audit_api import bp as audit_bp
    from .api.auth_api import bp as auth_bp
    from .api.care_api import bp as care_bp
    from .api.chat_api import bp as chat_bp
    from .api.dashboard_api import bp as dashboard_bp
    from .api.materials_api import bp as materials_bp
    from .api.wrong_api import bp as wrong_bp
    from . import pages

    app.register_blueprint(auth_bp)
    app.register_blueprint(assignments_bp)
    app.register_blueprint(wrong_bp)
    app.register_blueprint(care_bp)
    app.register_blueprint(analytics_bp)
    app.register_blueprint(audit_bp)
    app.register_blueprint(materials_bp)
    app.register_blueprint(assistant_bp)
    app.register_blueprint(chat_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(pages.bp)

    @app.before_request
    def before_request():
        g.audit_started_at = time.perf_counter()
        g.audit_error = False
        g.current_user = load_current_user()

    @app.after_request
    def after_request(response):
        record_api(response)
        return response

    @app.context_processor
    def inject_globals():
        user = getattr(g, "current_user", None)
        nav = NAV_ITEMS.get(user.role, []) if user else []
        return {
            "current_user": user,
            "nav_items": nav,
            "subjects": SUBJECTS,
            "subject_icons": SUBJECT_ICONS,
        }

    @app.get("/healthz")
    def healthz():
        db_ok = True
        redis_ok = True
        try:
            db.session.execute(db.text("SELECT 1"))
        except Exception:  # noqa: BLE001
            db_ok = False
        try:
            import redis

            client = redis.Redis.from_url(app.config["REDIS_URL"], socket_connect_timeout=2)
            client.ping()
        except Exception:  # noqa: BLE001
            redis_ok = False
        status = 200 if db_ok else 503
        return (
            jsonify(
                {
                    "status": "ok" if db_ok else "degraded",
                    "db": db_ok,
                    "redis": redis_ok,
                    "audit_failures": audit_failure_count(),
                    "time": datetime.utcnow().isoformat() + "Z",
                }
            ),
            status,
        )

    @app.errorhandler(404)
    def not_found(_error):
        if request.path.startswith("/api/"):
            return jsonify({"error": "资源不存在", "error_code": "not_found"}), 404
        return render_template("error.html", status=404, message="页面不存在"), 404

    @app.errorhandler(403)
    def forbidden(_error):
        if request.path.startswith("/api/"):
            return jsonify({"error": "无权限访问该资源", "error_code": "forbidden"}), 403
        return render_template("error.html", status=403, message="无权限访问该页面"), 403

    @app.errorhandler(500)
    def server_error(_error):
        g.audit_error = True
        if request.path.startswith("/api/"):
            return jsonify({"error": "服务暂时不可用", "error_code": "server_error"}), 500
        return render_template("error.html", status=500, message="服务暂时不可用"), 500

    return app
