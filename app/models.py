import json
from datetime import datetime

from .extensions import db

SUBJECTS = ["数学", "语文", "英语", "物理", "化学"]
SUBJECT_ICONS = {
    "数学": "🔢",
    "语文": "📖",
    "英语": "🔤",
    "物理": "⚛️",
    "化学": "🧪",
}


class SchoolClass(db.Model):
    __tablename__ = "school_classes"

    id = db.Column(db.String(32), primary_key=True)
    name = db.Column(db.String(64), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {"id": self.id, "name": self.name}


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.String(48), primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    display_name = db.Column(db.String(64), nullable=False)
    role = db.Column(db.String(16), nullable=False)
    class_id = db.Column(db.String(32), db.ForeignKey("school_classes.id"), nullable=True)
    avatar = db.Column(db.String(16), default="🧑‍🎓")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    school_class = db.relationship("SchoolClass", lazy="joined")

    def to_public_dict(self):
        return {
            "id": self.id,
            "username": self.username,
            "display_name": self.display_name,
            "role": self.role,
            "class_id": self.class_id,
            "class_name": self.school_class.name if self.school_class else None,
            "avatar": self.avatar,
        }


def _json_load(raw, default):
    if not raw:
        return default
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return default


class Material(db.Model):
    __tablename__ = "materials"

    id = db.Column(db.Integer, primary_key=True)
    class_id = db.Column(db.String(32), nullable=False, index=True)
    subject = db.Column(db.String(16), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_by = db.Column(db.String(48), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    chunks = db.relationship(
        "MaterialChunk", backref="material", cascade="all, delete-orphan", lazy="select"
    )

    def to_dict(self, with_chunks=False):
        data = {
            "id": self.id,
            "class_id": self.class_id,
            "subject": self.subject,
            "title": self.title,
            "chunk_count": len(self.chunks),
            "created_at": self.created_at.isoformat() + "Z",
        }
        if with_chunks:
            data["content"] = self.content
            data["chunks"] = [c.to_dict() for c in self.chunks]
        return data


class MaterialChunk(db.Model):
    __tablename__ = "material_chunks"

    id = db.Column(db.Integer, primary_key=True)
    material_id = db.Column(db.Integer, db.ForeignKey("materials.id"), nullable=False, index=True)
    class_id = db.Column(db.String(32), nullable=False, index=True)
    subject = db.Column(db.String(16), nullable=False)
    chunk_no = db.Column(db.Integer, nullable=False)
    text = db.Column(db.Text, nullable=False)

    def to_dict(self):
        return {
            "id": self.id,
            "material_id": self.material_id,
            "material_title": self.material.title if self.material else None,
            "chunk_no": self.chunk_no,
            "text": self.text,
        }


class Skill(db.Model):
    __tablename__ = "skills"
    __table_args__ = (db.UniqueConstraint("class_id", "skill_key", name="uq_skill_class_key"),)

    id = db.Column(db.Integer, primary_key=True)
    class_id = db.Column(db.String(32), nullable=False, index=True)
    skill_key = db.Column(db.String(48), nullable=False)
    name = db.Column(db.String(64), nullable=False)
    trigger_condition = db.Column(db.String(200), nullable=False, default="")
    behavior = db.Column(db.String(300), nullable=False, default="")
    prompt = db.Column(db.Text, nullable=False, default="")
    enabled = db.Column(db.Boolean, default=True, nullable=False)
    required = db.Column(db.Boolean, default=False, nullable=False)
    tools = db.Column(db.Text, default="[]")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self, include_prompt=False):
        data = {
            "id": self.id,
            "class_id": self.class_id,
            "skill_key": self.skill_key,
            "name": self.name,
            "trigger_condition": self.trigger_condition,
            "behavior": self.behavior,
            "enabled": bool(self.enabled),
            "required": bool(self.required),
            "tools": _json_load(self.tools, []),
        }
        if include_prompt:
            data["prompt"] = self.prompt
        return data


class McpServer(db.Model):
    __tablename__ = "mcp_servers"

    id = db.Column(db.Integer, primary_key=True)
    class_id = db.Column(db.String(32), nullable=False, index=True)
    name = db.Column(db.String(80), nullable=False)
    url = db.Column(db.String(200), nullable=False)
    status = db.Column(db.String(16), default="disconnected")
    tools = db.Column(db.Text, default="[]")
    builtin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "class_id": self.class_id,
            "name": self.name,
            "url": self.url,
            "status": self.status,
            "tools": _json_load(self.tools, []),
            "builtin": bool(self.builtin),
        }


class ChatMessage(db.Model):
    """学科助手对话，role = user / assistant。"""

    __tablename__ = "chat_messages"

    id = db.Column(db.Integer, primary_key=True)
    class_id = db.Column(db.String(32), nullable=False, index=True)
    student_id = db.Column(db.String(48), nullable=False, index=True)
    subject = db.Column(db.String(16), nullable=False)
    role = db.Column(db.String(16), nullable=False)
    content = db.Column(db.Text, nullable=False)
    skill_key = db.Column(db.String(48), nullable=True)
    sources = db.Column(db.Text, default="[]")
    trace = db.Column(db.Text, default="[]")
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    def to_dict(self):
        return {
            "id": self.id,
            "role": self.role,
            "content": self.content,
            "subject": self.subject,
            "skill_key": self.skill_key,
            "sources": _json_load(self.sources, []),
            "trace": _json_load(self.trace, []),
            "created_at": self.created_at.isoformat() + "Z",
        }


class CareMessage(db.Model):
    """关怀式对话独立存储，与学科对话完全分离。"""

    __tablename__ = "care_messages"

    id = db.Column(db.Integer, primary_key=True)
    class_id = db.Column(db.String(32), nullable=False, index=True)
    student_id = db.Column(db.String(48), nullable=False, index=True)
    role = db.Column(db.String(16), nullable=False)
    content = db.Column(db.Text, nullable=False)
    safety = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    def to_dict(self):
        return {
            "id": self.id,
            "role": self.role,
            "content": self.content,
            "safety": bool(self.safety),
            "created_at": self.created_at.isoformat() + "Z",
        }


class Assignment(db.Model):
    __tablename__ = "assignments"
    __table_args__ = (db.Index("ix_assignments_class_created", "class_id", "created_at"),)

    id = db.Column(db.Integer, primary_key=True)
    class_id = db.Column(db.String(32), nullable=False, index=True)
    subject = db.Column(db.String(16), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False, default="")
    deadline = db.Column(db.DateTime, nullable=False)
    created_by = db.Column(db.String(48), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "class_id": self.class_id,
            "subject": self.subject,
            "title": self.title,
            "description": self.description,
            "deadline": self.deadline.isoformat() + "Z",
            "created_at": self.created_at.isoformat() + "Z",
        }


class Submission(db.Model):
    __tablename__ = "submissions"
    __table_args__ = (
        db.UniqueConstraint(
            "assignment_id", "student_id", "idempotency_key", name="uq_submission_idempotency"
        ),
        db.Index("ix_submissions_class_created", "class_id", "created_at"),
    )

    id = db.Column(db.Integer, primary_key=True)
    assignment_id = db.Column(db.Integer, db.ForeignKey("assignments.id"), nullable=False)
    student_id = db.Column(db.String(48), nullable=False, index=True)
    class_id = db.Column(db.String(32), nullable=False, index=True)
    content = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(16), nullable=False, default="pending")
    ai_score = db.Column(db.Integer, nullable=True)
    ai_comment = db.Column(db.Text, nullable=True)
    ai_evidence = db.Column(db.Text, default="[]")
    teacher_score = db.Column(db.Integer, nullable=True)
    teacher_comment = db.Column(db.Text, nullable=True)
    is_wrong = db.Column(db.Boolean, default=False)
    idempotency_key = db.Column(db.String(80), nullable=False)
    error_message = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    graded_at = db.Column(db.DateTime, nullable=True)

    assignment = db.relationship("Assignment", lazy="joined")
    student = db.relationship(
        "User",
        lazy="joined",
        primaryjoin="Submission.student_id == User.id",
        foreign_keys="Submission.student_id",
    )

    def final_score(self):
        return self.teacher_score if self.teacher_score is not None else self.ai_score

    def to_dict(self):
        return {
            "id": self.id,
            "assignment_id": self.assignment_id,
            "assignment_title": self.assignment.title if self.assignment else None,
            "subject": self.assignment.subject if self.assignment else None,
            "student_id": self.student_id,
            "student_name": self.student.display_name if self.student else None,
            "content": self.content,
            "status": self.status,
            "ai_score": self.ai_score,
            "ai_comment": self.ai_comment,
            "ai_evidence": _json_load(self.ai_evidence, []),
            "teacher_score": self.teacher_score,
            "teacher_comment": self.teacher_comment,
            "final_score": self.final_score(),
            "is_wrong": bool(self.is_wrong),
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat() + "Z",
            "graded_at": self.graded_at.isoformat() + "Z" if self.graded_at else None,
        }


class WrongQuestion(db.Model):
    __tablename__ = "wrong_questions"
    __table_args__ = (
        db.UniqueConstraint("submission_id", "question_no", name="uq_wrong_submission_question"),
        db.Index("ix_wrong_class_created", "class_id", "created_at"),
    )

    id = db.Column(db.Integer, primary_key=True)
    submission_id = db.Column(db.Integer, db.ForeignKey("submissions.id"), nullable=False)
    student_id = db.Column(db.String(48), nullable=False, index=True)
    class_id = db.Column(db.String(32), nullable=False, index=True)
    subject = db.Column(db.String(16), nullable=False)
    question_no = db.Column(db.Integer, default=1)
    question_text = db.Column(db.Text, nullable=False)
    my_answer = db.Column(db.Text, nullable=False)
    error_reason = db.Column(db.Text, nullable=False)
    explanation = db.Column(db.Text, nullable=True)
    explained_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    submission = db.relationship("Submission", lazy="joined")

    def to_dict(self):
        return {
            "id": self.id,
            "submission_id": self.submission_id,
            "student_id": self.student_id,
            "subject": self.subject,
            "question_no": self.question_no,
            "question_text": self.question_text,
            "my_answer": self.my_answer,
            "error_reason": self.error_reason,
            "explanation": _json_load(self.explanation, None),
            "explained_at": self.explained_at.isoformat() + "Z" if self.explained_at else None,
            "created_at": self.created_at.isoformat() + "Z",
        }


class AuditLog(db.Model):
    __tablename__ = "audit_logs"
    __table_args__ = (db.Index("ix_audit_class_skill_created", "class_id", "skill", "created_at"),)

    id = db.Column(db.Integer, primary_key=True)
    class_id = db.Column(db.String(32), nullable=True, index=True)
    user_id = db.Column(db.String(48), nullable=True, index=True)
    skill = db.Column(db.String(48), nullable=True, index=True)
    action = db.Column(db.String(200), nullable=False, default="")
    params = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(16), nullable=False, default="success")
    duration_ms = db.Column(db.Integer, default=0)
    tokens = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    def to_dict(self):
        return {
            "id": self.id,
            "class_id": self.class_id,
            "user_id": self.user_id,
            "skill": self.skill,
            "action": self.action,
            "params": _json_load(self.params, {}),
            "status": self.status,
            "duration_ms": self.duration_ms,
            "tokens": self.tokens,
            "created_at": self.created_at.isoformat() + "Z",
        }
