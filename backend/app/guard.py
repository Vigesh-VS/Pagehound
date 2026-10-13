import re
import secrets
import unicodedata

REFUSAL = (
    "I can only help with questions about your uploaded documents. "
    "I can't share or change how I'm set up, but ask me anything about the files."
)

CANARY = f"PH-{secrets.token_hex(6)}"

_INVISIBLE = re.compile(r"[​-‏‪-‮⁠-⁤﻿]")

_OVERRIDE = [
    r"\b(ignore|disregard|forget|skip|bypass|override)\b.{0,40}\b(previous|prior|above|earlier|preceding|all|any|your|system|initial|original)\b.{0,30}\b(instructions?|rules?|prompts?|guidelines?|directions?|constraints?|messages?)\b",
    r"\byou are (now|no longer)\b",
    r"\b(act|behave|respond|answer) as (if you were|an?|the)\b.{0,40}\b(ai|assistant|model|bot|gpt|dan|developer|admin|system)\b",
    r"\bpretend (to be|you are|you're)\b",
    r"\b(developer|dev|god|admin|debug|jailbreak|unrestricted|dan) mode\b",
    r"\bjailbreak",
    r"\bnew (system )?(instructions?|rules?|persona|role)\b",
    r"\bfrom now on\b.{0,40}\b(you|your)\b",
]

_EXTRACT_VERBS = r"(reveal|show|print|repeat|read|recite|tell|give|list|output|display|share|leak|copy|dump|write|spell|translate|summari[sz]e|paraphrase|encode|what (is|are|were)|whats)"
_EXTRACT_TARGETS = r"(system prompt|system message|system instructions?|initial prompt|hidden prompt|original prompt|developer (message|prompt|instructions?)|pre-?prompt|meta ?prompt|(your|ur|the assistant'?s?|the model'?s?) (instructions?|rules|prompt|guidelines|directives|configuration|setup|system message)|(text|words|everything|instructions?|messages?) (above|before) (this|that|my)|what (you were|were you) (told|instructed|given))"

_EXTRACT = [
    rf"\b{_EXTRACT_VERBS}\b.{{0,60}}\b{_EXTRACT_TARGETS}",
    rf"\b{_EXTRACT_TARGETS}\b.{{0,40}}\b(verbatim|word for word|exactly|in full|as is)\b",
    r"\b(repeat|print|output)\b.{0,20}\b(verbatim|word for word)\b",
    r"\bhow (were|are) you (programmed|instructed|configured|prompted|set up)\b",
    r"\bwhat (were|have) you (been )?(told|instructed|given|programmed)\b",
]

_DOC_WORDS = re.compile(r"\b(document|pdf|file|paper|article|report|slides?|chapter|section|excerpt|text says|according to)\b")

_TAGS = re.compile(r"</?\s*(document_excerpts|excerpt|conversation|turn|question|system|instructions?)\b[^>]*>", re.I)


def normalize(text):
    text = unicodedata.normalize("NFKC", text or "")
    text = _INVISIBLE.sub("", text).lower()
    return re.sub(r"\s+", " ", text).strip()


def classify(text):
    t = normalize(text)
    if any(re.search(p, t) for p in _OVERRIDE):
        return "override"
    for p in _EXTRACT:
        m = re.search(p, t)
        if m and not (_DOC_WORDS.search(t) and not re.search(r"\b(your|ur|you)\b", m.group(0))):
            return "extract"
    return None


def neutralize(text):
    return _TAGS.sub("[removed]", text or "")


def safe_history(history):
    return [turn for turn in history if not (turn.get("role") == "user" and classify(turn.get("text", "")))]


def _shingles(text, n=6):
    words = re.findall(r"[a-z0-9]+", normalize(text))
    return {" ".join(words[i:i + n]) for i in range(len(words) - n + 1)}


def leaks(reply, system_prompt, sources=()):
    if CANARY.lower() in normalize(reply):
        return True
    overlap = _shingles(reply) & _shingles(system_prompt)
    if sources:
        overlap -= set().union(*(_shingles(s.get("text", "")) for s in sources))
    return len(overlap) >= 2
