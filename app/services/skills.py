from ..extensions import db
from ..models import Skill


def get_skill(class_id, skill_key):
    return Skill.query.filter_by(class_id=class_id, skill_key=skill_key).first()


def skill_enabled(class_id, skill_key, default=True):
    skill = get_skill(class_id, skill_key)
    if skill is None:
        return default
    return bool(skill.enabled)


def list_student_skills(class_id):
    """学生只读视图：名称、触发条件、启用状态，绝不返回提示词。"""
    skills = Skill.query.filter_by(class_id=class_id).order_by(Skill.id.asc()).all()
    return [skill.to_dict(include_prompt=False) for skill in skills]
