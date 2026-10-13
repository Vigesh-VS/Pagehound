import re

_FOLLOW_START = re.compile(
    r"^(and|also|but|so|then|what about|how about|and what|what else|why|how come|same|ok|okay|now)\b"
)
_REFERS_BACK = re.compile(
    r"\b(it|its|that|this|these|those|they|them|their|there|he|she|his|her|one|ones|above|previous|same|former|latter|more|further|else)\b"
)
_SELF_CONTAINED = re.compile(r"\b(document|pdf|file|chapter|section|page|slide|table|csv|summar\w*)\b")


def is_follow_up(question):
    q = " ".join(question.lower().split())
    words = q.split()
    if _FOLLOW_START.search(q):
        return True
    if len(words) <= 6 and _REFERS_BACK.search(q) and not _SELF_CONTAINED.search(q):
        return True
    return len(words) <= 3 and not _SELF_CONTAINED.search(q)


def contextualize(question, history):
    previous = next((t["text"] for t in reversed(history or []) if t.get("role") == "user" and t.get("text", "").strip()), "")
    if not previous or not is_follow_up(question):
        return question
    return f"{previous.strip()} {question.strip()}"


_SPLIT = re.compile(r"(?<=\?)\s+")


def split_questions(question, limit=8):
    parts = []
    for piece in (p.strip() for p in _SPLIT.split((question or "").strip())):
        if not piece:
            continue
        if parts and (not piece.endswith("?") or len(piece.split()) < 3):
            parts[-1] = f"{parts[-1]} {piece}"
        else:
            parts.append(piece)
    if len(parts) < 2:
        return [question]
    if len(parts) > limit:
        parts = parts[: limit - 1] + [" ".join(parts[limit - 1:])]
    return parts
