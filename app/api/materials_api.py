from flask import Blueprint, g, jsonify, request

from ..auth import json_error, role_required, valid_subject
from ..extensions import db
from ..models import Material, MaterialChunk, SUBJECTS
from ..retrieval import search_chunks

bp = Blueprint("materials_api", __name__, url_prefix="/api")


def _make_chunks(material, content):
    lines = [line.strip() for line in content.splitlines() if line.strip()]
    for index, line in enumerate(lines, start=1):
        db.session.add(
            MaterialChunk(
                material_id=material.id,
                class_id=material.class_id,
                subject=material.subject,
                chunk_no=index,
                text=line,
            )
        )
    return lines


@bp.get("/materials")
@role_required("student")
def materials():
    subject = request.args.get("subject", SUBJECTS[0])
    if not valid_subject(subject):
        return json_error("学科参数不合法", 400, "invalid_subject")
    items = (
        Material.query.filter_by(class_id=g.current_user.class_id, subject=subject)
        .order_by(Material.created_at.desc())
        .all()
    )
    return jsonify({"items": [item.to_dict() for item in items], "total": len(items), "subject": subject})


@bp.get("/materials/search")
@role_required("student")
def search():
    query = request.args.get("q", "").strip()
    subject = request.args.get("subject", SUBJECTS[0])
    if not valid_subject(subject):
        return json_error("学科参数不合法", 400, "invalid_subject")
    if not query:
        return jsonify({"items": [], "total": 0, "matched": False, "query": query})
    hits = search_chunks(g.current_user.class_id, subject, query)
    return jsonify({"items": hits, "total": len(hits), "matched": bool(hits), "query": query})


@bp.get("/materials/<int:material_id>")
@role_required("student")
def material_detail(material_id):
    material = Material.query.filter_by(
        id=material_id, class_id=g.current_user.class_id
    ).first()
    if material is None:
        return json_error("讲义不存在", 404, "not_found")
    return jsonify({"material": material.to_dict(with_chunks=True)})


@bp.get("/teacher/materials")
@role_required("teacher")
def teacher_materials():
    subject = request.args.get("subject", SUBJECTS[0])
    if not valid_subject(subject):
        return json_error("学科参数不合法", 400, "invalid_subject")
    items = (
        Material.query.filter_by(class_id=g.current_user.class_id, subject=subject)
        .order_by(Material.created_at.desc())
        .all()
    )
    return jsonify({"items": [item.to_dict() for item in items], "total": len(items), "subject": subject})


@bp.post("/teacher/materials")
@role_required("teacher")
def create_material():
    payload = request.get_json(silent=True) or {}
    subject = payload.get("subject")
    title = str(payload.get("title", "")).strip()
    content = str(payload.get("content", "")).strip()
    if not valid_subject(subject):
        return json_error("学科参数不合法", 400, "invalid_subject")
    if not title or len(title) > 200:
        return json_error("讲义标题必须为 1—200 字符", 400, "invalid_title")
    if not content:
        return json_error("讲义正文不能为空", 400, "invalid_content")

    material = Material(
        class_id=g.current_user.class_id,
        subject=subject,
        title=title,
        content=content,
        created_by=g.current_user.id,
    )
    db.session.add(material)
    db.session.flush()
    _make_chunks(material, content)
    db.session.commit()
    return jsonify({"material": material.to_dict()}), 201


@bp.delete("/teacher/materials/<int:material_id>")
@role_required("teacher")
def delete_material(material_id):
    material = Material.query.filter_by(
        id=material_id, class_id=g.current_user.class_id
    ).first()
    if material is None:
        return json_error("讲义不存在", 404, "not_found")
    db.session.delete(material)
    db.session.commit()
    return jsonify({"ok": True})
