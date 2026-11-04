"""本班词法检索：只检索真实切片，未命中就返回空列表。"""
import re

from .models import MaterialChunk


def _tokens(text):
    lowered = (text or "").lower()
    words = re.findall(r"[a-z0-9]+", lowered)
    chinese = re.findall(r"[\u4e00-\u9fa5]", lowered)
    bigrams = ["".join(chinese[i : i + 2]) for i in range(len(chinese) - 1)]
    return set(words + chinese + bigrams)


def search_chunks(class_id, subject, query, limit=3):
    """返回 [{material_id, material_title, chunk_no, text, relevance}]。"""
    tokens = _tokens(query)
    if not tokens:
        return []

    chunks = (
        MaterialChunk.query.filter_by(class_id=class_id, subject=subject)
        .order_by(MaterialChunk.material_id.asc(), MaterialChunk.chunk_no.asc())
        .all()
    )
    scored = []
    for chunk in chunks:
        haystack = chunk.text.lower()
        score = 0
        for token in tokens:
            count = haystack.count(token)
            if count:
                score += count * (3 if len(token) >= 2 else 1)
        if score:
            scored.append((score, chunk))

    if not scored:
        return []

    scored.sort(key=lambda item: item[0], reverse=True)
    max_score = scored[0][0]
    results = []
    for score, chunk in scored[:limit]:
        results.append(
            {
                "material_id": chunk.material_id,
                "material_title": chunk.material.title if chunk.material else "",
                "chunk_no": chunk.chunk_no,
                "text": chunk.text,
                "relevance": round(score / max_score, 2),
            }
        )
    return results
