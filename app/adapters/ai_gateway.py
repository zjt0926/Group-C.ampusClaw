"""课程 AI 网关适配层。

密钥只从服务端环境变量读取。未配置网关时启用本地演示生成器，
保证 Docker 环境可以完整走通批改、讲解、关怀、画像链路；
所有引用来源仍然只来自真实检索命中。
"""
import json
import re
import time

import requests
from flask import current_app


class AIGatewayError(Exception):
    pass


class AIGatewayTimeout(AIGatewayError):
    pass


class AIParseError(AIGatewayError):
    pass


def is_configured():
    return bool(
        current_app.config.get("AI_GATEWAY_BASE_URL") and current_app.config.get("AI_GATEWAY_API_KEY")
    )


def masked_key():
    key = current_app.config.get("AI_GATEWAY_API_KEY") or ""
    if not key:
        return "（未配置）"
    if len(key) <= 4:
        return "***"
    return key[:2] + "***" + key[-2:]


def chat_completion(messages, temperature=0.0):
    """调用 OpenAI 兼容的课程网关，返回 (文本, token 用量或 None)。"""
    base_url = current_app.config["AI_GATEWAY_BASE_URL"]
    timeout = current_app.config["AI_TIMEOUT_SECONDS"]
    url = base_url + "/chat/completions"
    payload = {
        "model": current_app.config["AI_GATEWAY_MODEL"],
        "messages": messages,
        "temperature": temperature,
    }
    try:
        response = requests.post(
            url,
            json=payload,
            headers={
                "Authorization": f"Bearer {current_app.config['AI_GATEWAY_API_KEY']}",
                "Content-Type": "application/json",
            },
            timeout=(5, timeout),
        )
    except requests.Timeout as exc:
        raise AIGatewayTimeout("模型调用超时") from exc
    except requests.RequestException as exc:
        raise AIGatewayError(f"模型网关请求失败: {exc}") from exc

    if response.status_code >= 400:
        raise AIGatewayError(f"模型网关返回 {response.status_code}")

    try:
        data = response.json()
        content = data["choices"][0]["message"]["content"]
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        raise AIGatewayError("模型返回结构无法解析") from exc

    usage = data.get("usage") or {}
    tokens = usage.get("total_tokens")
    return content, tokens


def _extract_json(text):
    if not text:
        raise AIParseError("模型返回为空")
    match = re.search(r"\{[\s\S]*\}", text)
    if not match:
        raise AIParseError("模型未返回 JSON")
    try:
        return json.loads(match.group(0))
    except ValueError as exc:
        raise AIParseError("模型返回非法 JSON") from exc


def _source_items(hits):
    return [
        {
            "material_id": hit["material_id"],
            "material_title": hit["material_title"],
            "chunk_no": hit["chunk_no"],
            "relevance": hit["relevance"],
        }
        for hit in hits
    ]


def _no_hit_note(hits):
    return "本班知识库未命中讲义。" if not hits else ""


def grade_submission(assignment, content, hits):
    """返回 {score, comment, evidence, is_wrong, tokens, mode}。

    分数越界或非法 JSON 抛 AIParseError，由上层按失败处理，绝不截断入库。
    """
    evidence = _source_items(hits)
    if is_configured():
        source_text = "\n".join(
            f"[{hit['material_title']} 片段{hit['chunk_no']}] {hit['text']}" for hit in hits
        ) or "（知识库未命中任何讲义，禁止编造来源）"
        messages = [
            {
                "role": "system",
                "content": (
                    "你是高中作业批改助手。必须只输出 JSON："
                    '{"score": 0-100 的整数, "comment": "评语", "is_wrong": true/false}。'
                    "评语要指出依据；若没有讲义来源，必须写明未命中，不得编造来源。"
                ),
            },
            {
                "role": "user",
                "content": (
                    f"作业题目：{assignment.title}\n{assignment.description}\n"
                    f"学生作答：{content}\n可用讲义：{source_text}"
                ),
            },
        ]
        text, tokens = chat_completion(messages, temperature=0.0)
        data = _extract_json(text)
        score = data.get("score")
        comment = data.get("comment")
        if not isinstance(score, int) or isinstance(score, bool) or not 0 <= score <= 100:
            raise AIParseError("模型返回分数不在 0—100 整数范围")
        if not isinstance(comment, str) or not comment.strip():
            raise AIParseError("模型返回评语为空")
        is_wrong = bool(data.get("is_wrong", score < current_app.config["PASS_SCORE"]))
        return {
            "score": score,
            "comment": comment.strip(),
            "evidence": evidence,
            "is_wrong": is_wrong,
            "tokens": tokens,
            "mode": "gateway",
        }

    return _mock_grade(assignment, content, hits)


def _mock_grade(assignment, content, hits):
    trimmed = content.strip()
    score = 68
    comment = "作答基本合理，可进一步补充依据与关键判断过程。"
    is_wrong = False

    if len(trimmed) < 20:
        score = 45
        comment = "作答过于简略，未给出必要的推导过程，无法支撑结论。"
        is_wrong = True
    elif any(word in trimmed for word in ("求根公式", "因式", "判别式")) and "2" in trimmed and "3" in trimmed:
        score = 90
        comment = "方法与结论基本正确，过程清晰；可再写明判别式符号的判断依据。"
    elif "用十字相乘得" in trimmed:
        score = 82
        comment = "方法正确，因式分解与判别式判断到位，可补充求根公式验证。"
    elif "单调" in trimmed and ("减" in trimmed or "增" in trimmed):
        score = 55
        comment = "结论方向可疑，建议用作差法或导数重新验证单调区间。"
        is_wrong = True
    elif trimmed:
        score = 68

    if hits:
        titles = "、".join(f"《{hit['material_title']}》片段{hit['chunk_no']}" for hit in hits)
        comment += f" 依据本班讲义：{titles}。"
    else:
        comment += " 本班知识库未命中讲义，本次评语不引用任何讲义来源。"

    return {
        "score": score,
        "comment": comment,
        "evidence": _source_items(hits),
        "is_wrong": is_wrong,
        "tokens": None,
        "mode": "local-demo",
    }


def explain_wrong_question(question, hits):
    if is_configured():
        source_text = "\n".join(
            f"[{hit['material_title']} 片段{hit['chunk_no']}] {hit['text']}" for hit in hits
        ) or "（知识库未命中任何讲义，禁止编造来源）"
        messages = [
            {
                "role": "system",
                "content": (
                    "你是错题讲解助手。必须只输出 JSON："
                    '{"error_analysis": "错因分析", "knowledge_points": ["知识点1"], '
                    '"advice": "修正建议"}。三段都必须非空。'
                    "默认不给最终答案，以引导重做思路为主；没有讲义来源时写明未命中，不得编造。"
                ),
            },
            {
                "role": "user",
                "content": (
                    f"题目：{question.question_text}\n学生作答：{question.my_answer}\n"
                    f"AI 错因：{question.error_reason}\n可用讲义：{source_text}"
                ),
            },
        ]
        text, tokens = chat_completion(messages, temperature=0.3)
        data = _extract_json(text)
        error_analysis = data.get("error_analysis")
        knowledge_points = data.get("knowledge_points")
        advice = data.get("advice")
        if not (
            isinstance(error_analysis, str)
            and error_analysis.strip()
            and isinstance(knowledge_points, list)
            and knowledge_points
            and isinstance(advice, str)
            and advice.strip()
        ):
            raise AIParseError("讲解三段式结构不完整")
        kp = [
            {
                "title": str(item),
                "material_title": hit["material_title"],
                "chunk_no": hit["chunk_no"],
                "relevance": hit["relevance"],
            }
            for item, hit in zip(knowledge_points, hits)
        ] if hits else []
        return {
            "error_analysis": error_analysis.strip(),
            "knowledge_points": kp,
            "advice": advice.strip(),
            "no_hit": not hits,
            "tokens": tokens,
            "mode": "gateway",
        }

    kp = [
        {
            "title": hit["text"][:28],
            "material_title": hit["material_title"],
            "chunk_no": hit["chunk_no"],
            "relevance": hit["relevance"],
        }
        for hit in hits
    ]
    advice = "请回到定义，逐步重做：先写出关键判断（如判别式或单调性依据），再得出结论。这里不直接给出最终答案。"
    error = question.error_reason or "作答过程缺少关键判断。"
    return {
        "error_analysis": f"本题失分主要在于：{error}。",
        "knowledge_points": kp,
        "advice": advice,
        "no_hit": not hits,
        "tokens": None,
        "mode": "local-demo",
    }


def tutor_reply(question, hits, skill_enabled):
    if is_configured():
        source_text = "\n".join(
            f"[{hit['material_title']} 片段{hit['chunk_no']}] {hit['text']}" for hit in hits
        ) or "（知识库未命中任何讲义，禁止编造来源）"
        system = (
            "你是高一学科学习助手。回答须严谨、循序渐进。"
            "若解题引导开启，先引导学生思考，不直接给最终答案；"
            "所有结论尽量给出讲义来源，没有来源时明确说明未命中。"
        )
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": f"问题：{question}\n可用讲义：{source_text}"},
        ]
        text, tokens = chat_completion(messages, temperature=0.4)
        return text.strip(), tokens, "gateway"

    if not hits:
        text = (
            "在本班知识库中没有检索到与该问题直接相关的资料，"
            "因此我不能凭空给出结论。建议你补充题目条件，或让老师上传相关讲义后再试。"
        )
    elif skill_enabled:
        text = (
            "我们一起理清思路，这里先不直接给最终答案。\n"
            "1. 回顾相关知识，先想想题目给了哪些条件；\n"
            "2. 可以先判断关键量（如判别式或单调区间）；\n"
            "3. 试着写出第一步推导，把结果发给我，我来帮你检查方向是否正确。\n"
            "如果需要，我也可以给出完整的解题步骤。"
        )
    else:
        text = (
            "解题引导技能当前已关闭，我直接为你讲解：\n"
            "先整理题目条件，再选择合适的公式或方法，最后代入计算并检验结果。\n"
            "本回答依据本班讲义内容生成。"
        )
    return text, None, "local-demo"


def care_reply(message):
    if is_configured():
        messages = [
            {
                "role": "system",
                "content": (
                    "你是学校里的关怀式对话助手，只关注学生的情绪与学习状态。"
                    "不回答学科题目，不引用讲义，不给知识性解答。"
                    "先共情，再给出可执行的小步骤；持续负面情绪时建议联系班主任、心理老师或家人。"
                ),
            },
            {"role": "user", "content": message},
        ]
        text, tokens = chat_completion(messages, temperature=0.5)
        return text.strip(), tokens, "gateway"

    if any(word in message for word in ("考砸", "没用", "放弃", "失败", "学不好")):
        text = (
            "听起来你现在有点低落，辛苦了。遇到难题会让人怀疑自己，但这并不代表你不够好。"
            "进步很少是直线，一次没做好，只是还没找到适合你的方法。"
            "我们可以从你已经会的那一步重新出发：今天先挑一道最有把握的题，做完后记下用到的知识点。"
            "如果这种感觉持续影响睡眠或上课，建议和班主任或心理老师聊一聊。"
        )
    elif any(word in message for word in ("焦虑", "紧张", "压力", "睡不着", "担心")):
        text = (
            "我能感受到你现在有些紧张和压力。先和我一起做个深呼吸：吸气 4 秒，屏住 2 秒，再慢慢呼气 6 秒。"
            "压力往往说明你很在意结果，这本身是件好事。"
            "我们可以把担心的事情一条条写下来，再挑一件现在就能着手的小事去做。"
            "你愿意告诉我，最让你焦虑的是哪一件吗？我们一起把它拆小。"
        )
    else:
        text = (
            "你好，这里是你的学习空间。你可以说说今天的状态，比如哪一科让你最有压力，"
            "或者哪件事让你开心。我会先听你说，不急着给结论。"
        )
    return text, None, "local-demo"


def learning_profile(stats, weak_topics):
    if is_configured():
        messages = [
            {
                "role": "system",
                "content": (
                    "你是学情分析助手。只依据给定聚合数字与错题主题生成学习画像，"
                    "输出 JSON：{\"style\":\"学习风格\",\"strengths\":[\"强科\"],"
                    "\"weaknesses\":[\"待提升\"],\"advice\":\"至少一条具体建议\"}。"
                    "不得引用任何其他学生信息或原始作答全文。"
                ),
            },
            {
                "role": "user",
                "content": json.dumps({"stats": stats, "weak_topics": weak_topics}, ensure_ascii=False),
            },
        ]
        text, tokens = chat_completion(messages, temperature=0.4)
        data = _extract_json(text)
        return {
            "style": str(data.get("style", "")).strip(),
            "strengths": [str(item) for item in data.get("strengths", [])][:5],
            "weaknesses": [str(item) for item in data.get("weaknesses", [])][:5],
            "advice": str(data.get("advice", "")).strip(),
            "tokens": tokens,
            "mode": "gateway",
        }

    mastery = stats.get("mastery", {})
    strong = [subject for subject, value in mastery.items() if isinstance(value, (int, float)) and value >= 80]
    weak = [subject for subject, value in mastery.items() if isinstance(value, (int, float)) and value < 60]
    style = "稳健推导型" if stats.get("submissions", 0) >= 3 else "起步探索型"
    advice = "建议优先巩固错题集中的学科要点，多做基础题，同时保持优势学科的学习节奏。"
    if weak_topics:
        advice = f"建议优先巩固{ '、'.join(weak_topics[:2]) }相关的错题要点，每道错题按“错因—知识点—重做”三步复盘。"
    return {
        "style": style,
        "strengths": strong or [],
        "weaknesses": weak or [],
        "advice": advice,
        "tokens": None,
        "mode": "local-demo",
    }


def timed(fn):
    started = time.perf_counter()
    try:
        result = fn()
        return result, int((time.perf_counter() - started) * 1000), "success"
    except AIGatewayTimeout as exc:
        return exc, int((time.perf_counter() - started) * 1000), "timeout"
    except Exception as exc:  # noqa: BLE001
        return exc, int((time.perf_counter() - started) * 1000), "error"
