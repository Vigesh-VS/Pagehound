from . import config, embeddings
from .query import contextualize, split_questions
from .retrieval import gather_many


def find_sources(docs, question, history):
    parts = split_questions(question) if config.SPLIT_QUESTIONS else [question]
    searches = []
    for n, part in enumerate(parts):
        earlier = list(history) + [{"role": "user", "text": p} for p in parts[:n]]
        search = contextualize(part, earlier) if config.REWRITE_FOLLOW_UPS else part
        searches.append((embeddings.embed_query(search), search))
    return gather_many(docs, searches, question)
