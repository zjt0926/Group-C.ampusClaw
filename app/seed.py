"""幂等种子数据：班级、账号、讲义、作业、技能、MCP 与一条演示批改结果。"""
import json
from datetime import datetime, timedelta

from werkzeug.security import generate_password_hash

from . import create_app
from .extensions import db
from .models import (
    Assignment,
    Material,
    MaterialChunk,
    McpServer,
    SchoolClass,
    Skill,
    Submission,
    User,
    WrongQuestion,
)

PASSWORD = "Campus@123"


def _make_chunks(material, lines):
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


MATERIALS = {
    "cls-a": [
        (
            "数学",
            "一元二次方程与求根公式",
            [
                "一元二次方程的一般形式为 ax²+bx+c=0（a≠0）。",
                "求根公式为 x = [-b ± √(b²-4ac)] / (2a)。",
                "判别式 Δ=b²-4ac：Δ>0 有两个不相等实根，Δ=0 有两个相等实根，Δ<0 无实根。",
                "使用求根公式前先判断判别式符号，再代入计算。",
                "例题：用求根公式解 x²-5x+6=0。这里 a=1，b=-5，c=6，Δ=25-24=1，所以 x=(5±1)/2，得到 x₁=3，x₂=2。",
                "当方程可因式分解时，也可优先用十字相乘法：x²-5x+6=(x-2)(x-3)。",
            ],
        ),
        (
            "语文",
            "文言文实词与虚词",
            [
                "词类活用指某类词临时用作他类，如名词作动词、使动、意动。",
                "“衣锦还乡”中的“衣”是名词作动词，意为“穿”。",
                "常见虚词“之”的用法：作代词代人/事；作助词用于主谓之间取消句子独立性；作宾语前置的标志。",
                "翻译句子先找主干，再判断词类活用与特殊句式。",
                "《劝学》中“君子生非异也，善假于物也”，注意“生”通“性”。",
            ],
        ),
        (
            "英语",
            "时态与语态",
            [
                "一般现在时表经常或事实，第三人称单数动词加 -s。",
                "一般过去时表过去动作，规则动词加 -ed。",
                "被动语态结构为 be + 过去分词，强调动作的承受者。",
                "阅读主旨题关注首末段与主题句，避免以偏概全。",
                "推理判断题需基于原文信息合理延伸，注意作者态度词。",
            ],
        ),
        (
            "物理",
            "匀变速直线运动",
            [
                "匀变速直线运动速度公式 v = v₀ + at。",
                "位移公式 x = v₀t + ½at²；不含时间时可用 v² - v₀² = 2ax。",
                "加速度方向与速度变化方向一致。",
                "受力分析先隔离研究对象，依次找重力、支持力、摩擦力、拉力等。",
                "牛顿第二定律：物体加速度与所受合外力成正比，与质量成反比，方向与合力方向相同。",
            ],
        ),
        (
            "化学",
            "物质的量与摩尔",
            [
                "物质的量单位为摩尔（mol），1 mol 任何粒子含约 6.02×10²³ 个粒子。",
                "摩尔质量 M 在数值上等于相对分子或原子质量，单位 g/mol。",
                "物质的量 n = m / M。",
                "化学方程式配平依据质量守恒：反应前后各元素原子个数相等。",
                "常用观察法与最小公倍数法：先配变化大的元素，再逐步调整系数。",
            ],
        ),
    ],
    "cls-b": [
        (
            "数学",
            "集合与常用逻辑用语",
            [
                "集合的基本运算包括交集、并集、补集。",
                "注意空集是任何集合的子集，讨论子集时不能漏掉空集。",
                "若 p 推出 q，则 p 是 q 的充分条件，q 是 p 的必要条件。",
                "若 p 与 q 互为充分必要条件，则 p 是 q 的充要条件。",
            ],
        ),
    ],
}

ASSIGNMENTS = {
    "cls-a": [
        ("数学", "用求根公式解 x²-5x+6=0", "请写出判别式并说明所用方法，给出两个根。", 7),
        ("语文", "记叙文阅读概括主旨", "阅读一段写景文字，概括其主旨并赏析其中一处修辞。", 10),
        ("英语", "时态填空练习", "用所给动词的正确时态填空并说明理由，至少含一句被动语态。", 5),
        ("物理", "汽车加速运动学计算", "汽车以初速度 v₀ 加速，求一段时间后的速度与位移。", 6),
        ("化学", "计算水的物质的量", "求 18 g 水的物质的量与所含分子数，并说明计算依据。", 9),
    ],
    "cls-b": [
        ("数学", "集合运算练习", "已知集合 A 与 B，求交集、并集与补集，并说明空集的情况。", 7),
    ],
}

SKILLS = [
    {
        "skill_key": "tutor_hint",
        "name": "解题引导",
        "trigger_condition": "学生就题目提问",
        "behavior": "追问思路、引用知识库，默认不直接给最终答案",
        "prompt": (
            "你是高一学科学习助手。回答须严谨、循序渐进。"
            "若开启解题引导，则先引导学生思考，不直接给出最终答案。"
            "所有结论尽量给出知识库来源；未命中讲义时明确说明，不得编造。"
        ),
        "enabled": True,
        "required": False,
        "tools": ["知识库检索"],
    },
    {
        "skill_key": "homework_grade",
        "name": "作业批改",
        "trigger_condition": "学生提交作业后",
        "behavior": "给出分数、评语与依据，教师可改分",
        "prompt": (
            "你是高中作业批改助手。按评分点给出 0—100 的整数分数与评语，"
            "并引用本班讲义作为依据；检索未命中时必须说明未命中，不得编造来源。"
        ),
        "enabled": True,
        "required": True,
        "tools": ["作业读取", "知识库检索"],
    },
    {
        "skill_key": "wrong_explain",
        "name": "错题讲解",
        "trigger_condition": "学生查看判错的题目",
        "behavior": "按错因讲解，默认不直接给最终答案",
        "prompt": (
            "你是错题讲解助手。输出三段：错因分析、相关知识点（带讲义来源）、修正建议。"
            "默认不给最终答案，以引导重做思路为主；未命中讲义时明确说明，不得编造。"
        ),
        "enabled": True,
        "required": False,
        "tools": ["作业读取", "知识库检索"],
    },
    {
        "skill_key": "care_chat",
        "name": "关怀式对话",
        "trigger_condition": "学生表达情绪或学习压力",
        "behavior": "先共情再建议，不接触讲义与学科知识",
        "prompt": (
            "你是学校里的关怀式对话助手，只关注学生的情绪与学习状态。"
            "不回答学科题目，不引用讲义，不给知识性解答。"
        ),
        "enabled": True,
        "required": False,
        "tools": [],
    },
]


def seed():
    if User.query.filter_by(username="teacher_a").first() is not None:
        return False

    db.session.add_all(
        [
            SchoolClass(id="cls-a", name="高一（3）班"),
            SchoolClass(id="cls-b", name="高一（5）班"),
        ]
    )
    db.session.flush()

    db.session.add_all(
        [
            User(
                id="u-teacher-a",
                username="teacher_a",
                password_hash=generate_password_hash(PASSWORD),
                display_name="张老师",
                role="teacher",
                class_id="cls-a",
                avatar="👩‍🏫",
            ),
            User(
                id="u-stu-a1",
                username="student_a1",
                password_hash=generate_password_hash(PASSWORD),
                display_name="李明（A1）",
                role="student",
                class_id="cls-a",
                avatar="🧑‍🎓",
            ),
            User(
                id="u-stu-a2",
                username="student_a2",
                password_hash=generate_password_hash(PASSWORD),
                display_name="陈晨（A2）",
                role="student",
                class_id="cls-a",
                avatar="🧑‍🦱",
            ),
            User(
                id="u-stu-b1",
                username="student_b1",
                password_hash=generate_password_hash(PASSWORD),
                display_name="王芳（B1）",
                role="student",
                class_id="cls-b",
                avatar="👧",
            ),
        ]
    )
    db.session.flush()

    math_material_a = None
    for class_id, items in MATERIALS.items():
        for subject, title, lines in items:
            material = Material(
                class_id=class_id,
                subject=subject,
                title=title,
                content="\n".join(lines),
                created_by="u-teacher-a",
            )
            db.session.add(material)
            db.session.flush()
            _make_chunks(material, lines)
            if class_id == "cls-a" and subject == "数学":
                math_material_a = material

    now = datetime.utcnow()
    assignment_records = {}
    for class_id, items in ASSIGNMENTS.items():
        for subject, title, description, days in items:
            assignment = Assignment(
                class_id=class_id,
                subject=subject,
                title=title,
                description=description,
                deadline=now + timedelta(days=days),
                created_by="u-teacher-a" if class_id == "cls-a" else None,
            )
            db.session.add(assignment)
            db.session.flush()
            assignment_records[(class_id, subject)] = assignment

    for class_id, items in [("cls-a", SKILLS)]:
        for item in items:
            db.session.add(
                Skill(
                    class_id=class_id,
                    skill_key=item["skill_key"],
                    name=item["name"],
                    trigger_condition=item["trigger_condition"],
                    behavior=item["behavior"],
                    prompt=item["prompt"],
                    enabled=item["enabled"],
                    required=item["required"],
                    tools=json.dumps(item["tools"], ensure_ascii=False),
                )
            )

    db.session.add_all(
        [
            McpServer(
                class_id="cls-a",
                name="知识库检索服务",
                url="mcp://campusclaw/knowledge-base",
                status="connected",
                tools=json.dumps(["kb.search", "kb.getChunk"], ensure_ascii=False),
                builtin=True,
            ),
            McpServer(
                class_id="cls-a",
                name="数学计算工具",
                url="mcp://tools/math-solver",
                status="connected",
                tools=json.dumps(["math.solveEquation", "math.plotFunction"], ensure_ascii=False),
                builtin=True,
            ),
        ]
    )

    # 演示用已批改提交：让首页/错题/学情页可直接看到真实数据库内容
    math_assignment = assignment_records[("cls-a", "数学")]
    submission = Submission(
        assignment_id=math_assignment.id,
        student_id="u-stu-a1",
        class_id="cls-a",
        content="我用因式分解得到 (x-2)(x-3)=0，所以 x=2 或 x=3。",
        status="graded",
        ai_score=55,
        ai_comment=(
            "因式分解结果正确，但未按要求写出判别式并说明所用方法，过程不完整。"
            " 依据本班讲义：《一元二次方程与求根公式》片段5。"
        ),
        ai_evidence=json.dumps(
            [
                {
                    "material_id": math_material_a.id,
                    "material_title": math_material_a.title,
                    "chunk_no": 5,
                    "relevance": 1.0,
                }
            ],
            ensure_ascii=False,
        ),
        is_wrong=True,
        idempotency_key="seed-a1-math-1",
        created_at=now - timedelta(days=1),
        graded_at=now - timedelta(days=1, minutes=-1),
    )
    db.session.add(submission)
    db.session.flush()
    db.session.add(
        WrongQuestion(
            submission_id=submission.id,
            student_id="u-stu-a1",
            class_id="cls-a",
            subject="数学",
            question_no=1,
            question_text=f"{math_assignment.title}\n{math_assignment.description}",
            my_answer=submission.content,
            error_reason="未按要求写出判别式并说明所用方法，过程不完整。",
            created_at=now - timedelta(days=1),
        )
    )

    submission2 = Submission(
        assignment_id=math_assignment.id,
        student_id="u-stu-a2",
        class_id="cls-a",
        content="Δ=(-5)²-4×1×6=1，所以 x=(5±1)/2，得到 x₁=3，x₂=2。",
        status="graded",
        ai_score=92,
        ai_comment=(
            "判别式与求根公式使用正确，过程完整，结论正确。"
            " 依据本班讲义：《一元二次方程与求根公式》片段2、5。"
        ),
        ai_evidence=json.dumps(
            [
                {
                    "material_id": math_material_a.id,
                    "material_title": math_material_a.title,
                    "chunk_no": 2,
                    "relevance": 1.0,
                }
            ],
            ensure_ascii=False,
        ),
        idempotency_key="seed-a2-math-1",
        created_at=now - timedelta(hours=20),
        graded_at=now - timedelta(hours=20, minutes=-1),
    )
    db.session.add(submission2)

    db.session.commit()
    return True


def main():
    app = create_app()
    with app.app_context():
        db.create_all()
        created = seed()
        print("种子数据已写入" if created else "种子数据已存在，跳过")


if __name__ == "__main__":
    main()
