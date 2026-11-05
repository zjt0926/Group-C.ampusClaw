from datetime import datetime

from ..adapters import ai_gateway
from ..audit import record_skill
from ..extensions import db
from ..models import CareMessage

RISK_WORDS = [
    "自杀",
    "轻生",
    "不想活",
    "结束生命",
    "自残",
    "割腕",
    "跳楼",
    "活不下去",
    "死了算了",
    "伤害自己",
]

SAFETY_TEXT = (
    "我很在意你现在的感受，你愿意说出来已经很不容易。此刻请先保证自己的安全："
    "远离危险物品，走到有人的地方，告诉身边信任的人。"
    "你可以联系班主任、学校心理老师，或拨打心理援助热线 12356。"
    "如果需要紧急帮助，请拨打 120 或 110。你并不孤单，我们会陪着你。"
)

HELP_CHANNELS = [
    "班主任：可在班级群里联系",
    "学校心理老师：工作日到心理辅导室",
    "心理援助热线：12356",
    "紧急情况：120 / 110",
]


class CareError(Exception):
    def __init__(self, message, error_code="bad_request"):
        super().__init__(message)
        self.message = message
        self.error_code = error_code


def history(class_id, student_id):
    messages = (
        CareMessage.query.filter_by(class_id=class_id, student_id=student_id)
        .order_by(CareMessage.created_at.asc())
        .all()
    )
    return [message.to_dict() for message in messages]


def _risk_hit(text):
    return [word for word in RISK_WORDS if word in text]


def handle_message(user, text):
    risk = _risk_hit(text)
    user_message = CareMessage(
        class_id=user.class_id,
        student_id=user.id,
        role="user",
        content=text,
        safety=bool(risk),
    )
    db.session.add(user_message)
    db.session.commit()

    started = datetime.utcnow()
    if risk:
        reply = SAFETY_TEXT
        safety = True
        record_skill(
            user,
            "care_chat",
            "care",
            "success",
            (datetime.utcnow() - started).total_seconds() * 1000,
            None,
            {"risk_hit": risk},
        )
        mode = "safety"
    else:
        try:
            reply, tokens, mode = ai_gateway.care_reply(text)
            record_skill(
                user,
                "care_chat",
                "care",
                "success",
                (datetime.utcnow() - started).total_seconds() * 1000,
                tokens,
                {"message_len": len(text)},
            )
        except Exception as exc:  # noqa: BLE001
            # 模型不可用时仍给出温和的安全回应，避免空白
            reply = (
                "我在听你说。现在先不用急着解决所有问题，"
                "可以试着深呼吸几次，把最困扰你的一件事写下来。"
                "如果情绪持续低落，建议找班主任或心理老师聊一聊。"
            )
            mode = "fallback"
            record_skill(
                user,
                "care_chat",
                "care",
                "timeout" if isinstance(exc, ai_gateway.AIGatewayTimeout) else "error",
                (datetime.utcnow() - started).total_seconds() * 1000,
                None,
                {"message_len": len(text)},
            )
        safety = False

    assistant_message = CareMessage(
        class_id=user.class_id,
        student_id=user.id,
        role="assistant",
        content=reply,
        safety=safety,
    )
    db.session.add(assistant_message)
    db.session.commit()
    return assistant_message.to_dict(), bool(risk), mode
