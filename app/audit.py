import json
import logging
import re
import time

from flask import g, request
from sqlalchemy.orm import sessionmaker

from .extensions import db
from .models import AuditLog

LOGGER = logging.getLogger(__name__)

AUDIT_STATE = {"failures": 0}

SENSITIVE_KEYS = {"password", "token", "access_token", "authorization", "api_key", "apikey", "secret"}
TRUNCATE_KEYS = {"content", "message", "text", "answer", "prompt", "comment"}
MAX_SUMMARY_CHARS = 200


def _sanitize_value(key, value):
    lowered = (key or "").lower()
    if lowered in SENSITIVE_KEYS or any(s in lowered for s in ("password", "api_key", "apikey", "authorization", "secret")):
        return "***"
    if isinstance(value, str):
        if lowered in TRUNCATE_KEYS or len(value) > MAX_SUMMARY_CHARS:
            return value[:MAX_SUMMARY_CHARS] + f"...(len={len(value)})"
        return value
    if isinstance(value, list):
        return [_sanitize_value(key, item) for item in value[:5]]
    if isinstance(value, dict):
        return sanitize_params(value)
    return value


def sanitize_params(data):
    if not isinstance(data, dict):
        return {}
    result = {}
    for key, value in list(data.items())[:20]:
        result[key] = _sanitize_value(key, value)
    return result


def _write(entry):
    """审计写入使用独立会话，失败只记 warning，不阻断业务。"""
    Session = sessionmaker(bind=db.engine)
    session = Session()
    try:
        session.add(AuditLog(**entry))
        session.commit()
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        AUDIT_STATE["failures"] += 1
        LOGGER.warning("审计写入失败: %s", exc)
    finally:
        session.close()


def record_api(response):
    if not request.path.startswith("/api/"):
        return
    try:
        user = getattr(g, "current_user", None)
        started = getattr(g, "audit_started_at", None)
        duration_ms = int((time.perf_counter() - started) * 1000) if started else 0
        status = "success"
        if response.status_code >= 500 or getattr(g, "audit_error", False):
            status = "error"
        elif response.status_code >= 400:
            status = "failed"

        params = {}
        if user is not None:
            query = {k: v for k, v in request.args.items()}
            if query:
                params["query"] = sanitize_params(query)
            if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
                payload = request.get_json(silent=True)
                if isinstance(payload, dict):
                    params["body"] = sanitize_params(payload)

        rule = request.url_rule.rule if request.url_rule is not None else request.path
        _write(
            {
                "class_id": user.class_id if user else None,
                "user_id": user.id if user else None,
                "skill": None,
                "action": f"{request.method} {rule}",
                "params": json.dumps(params, ensure_ascii=False) if params else None,
                "status": status,
                "duration_ms": duration_ms,
                "tokens": None,
            }
        )
    except Exception as exc:  # noqa: BLE001
        AUDIT_STATE["failures"] += 1
        LOGGER.warning("审计中间件异常: %s", exc)


def record_skill(user, skill, action, status, duration_ms, tokens=None, params=None):
    entry = {
        "class_id": user.class_id if user else None,
        "user_id": user.id if user else None,
        "skill": skill,
        "action": action,
        "params": json.dumps(sanitize_params(params or {}), ensure_ascii=False),
        "status": status,
        "duration_ms": int(duration_ms),
        "tokens": tokens,
    }
    _write(entry)


def audit_failure_count():
    return AUDIT_STATE["failures"]


SECRET_PATTERN = re.compile(r"(sk-[A-Za-z0-9]{16,}|api[_-]?key[\"']?\s*[:=]\s*[\"'][^\"']{8,})", re.I)
