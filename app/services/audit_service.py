from sqlalchemy import case, func, or_

from ..models import AuditLog, SUBJECTS, User


def summary(class_id):
    rows = (
        AuditLog.query.with_entities(
            AuditLog.skill,
            func.count(AuditLog.id).label("count"),
            func.sum(case((AuditLog.status != "success", 1), else_=0)).label("failures"),
            func.sum(AuditLog.tokens).label("tokens"),
        )
        .filter(AuditLog.class_id == class_id, AuditLog.skill.isnot(None))
        .group_by(AuditLog.skill)
        .order_by(AuditLog.skill.asc())
        .all()
    )
    result = []
    for skill, count, failures, tokens in rows:
        result.append(
            {
                "skill": skill,
                "count": int(count or 0),
                "fail_rate": round(float(failures or 0) / count, 3) if count else None,
                "tokens": int(tokens) if tokens is not None else None,
            }
        )
    return result


def overall(class_id):
    total = AuditLog.query.filter_by(class_id=class_id).count()
    failures = AuditLog.query.filter(
        AuditLog.class_id == class_id, AuditLog.status != "success"
    ).count()
    tokens = (
        AuditLog.query.with_entities(func.sum(AuditLog.tokens))
        .filter(AuditLog.class_id == class_id)
        .scalar()
    )
    skills = sorted(
        {
            row[0]
            for row in AuditLog.query.with_entities(AuditLog.skill)
            .filter(AuditLog.class_id == class_id, AuditLog.skill.isnot(None))
            .all()
        }
    )
    return {
        "total": total,
        "failures": failures,
        "tokens": int(tokens) if tokens is not None else None,
        "skills": skills,
    }


def list_logs(class_id, skill=None, status=None, start=None, end=None, page=1, page_size=20):
    query = AuditLog.query.filter(AuditLog.class_id == class_id)
    if skill:
        query = query.filter(AuditLog.skill == skill)
    if status:
        query = query.filter(AuditLog.status == status)
    if start:
        query = query.filter(AuditLog.created_at >= start)
    if end:
        query = query.filter(AuditLog.created_at <= end)

    total = query.count()
    page = max(1, int(page))
    page_size = min(100, max(1, int(page_size)))
    items = (
        query.order_by(AuditLog.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    user_names = {}
    user_ids = {item.user_id for item in items if item.user_id}
    if user_ids:
        for user in User.query.filter(User.id.in_(user_ids)).all():
            user_names[user.id] = user.display_name
    return {
        "items": [
            {**item.to_dict(), "user_name": user_names.get(item.user_id)}
            for item in items
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
        "skills": sorted(
            {
                row[0]
                for row in AuditLog.query.with_entities(AuditLog.skill)
                .filter(AuditLog.class_id == class_id, AuditLog.skill.isnot(None))
                .all()
            }
        ),
        "subjects": SUBJECTS,
    }
