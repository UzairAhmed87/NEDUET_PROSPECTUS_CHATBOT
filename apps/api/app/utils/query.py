from __future__ import annotations

import re

_TOKEN = re.compile(r"[a-z0-9]+")

ACRONYMS = {
    "csit": "computer science and information technology",
    "cis": "computer and information systems",
    "cse": "computer systems engineering",
    "tiest": "thar institute of engineering sciences and technology",
}

INTENT_EXPANSIONS: tuple[tuple[frozenset[str], str], ...] = (
    (
        frozenset({"fee", "fees", "tuition", "charges"}),
        "tuition fee charges fee structure semester admission fee",
    ),
    (
        frozenset({"department", "departments"}),
        "teaching departments faculty faculties academic programmes listed below",
    ),
    (
        frozenset({"programme", "programmes", "program", "programs"}),
        "undergraduate programmes bachelor of science bachelor of engineering academic programmes",
    ),
    (
        frozenset({"scholarship", "scholarships", "stipend", "stipends"}),
        "scholarships stipends awards financial assistance",
    ),
    (
        frozenset({"eligib", "eligibility", "eligible"}),
        "admission eligibility qualifying examination marks",
    ),
)

FOLLOWUP_PREFIXES = (
    "and ",
    "also ",
    "what about",
    "how about",
    "for that",
    "for those",
    "the same",
    "same for",
)
FOLLOWUP_PRONOUNS = {"it", "its", "they", "them", "those", "that", "this"}
_STOP = {
    "the",
    "and",
    "for",
    "are",
    "was",
    "were",
    "what",
    "when",
    "which",
    "how",
    "many",
    "there",
    "does",
    "about",
    "from",
    "with",
    "this",
    "that",
    "your",
    "not",
    "but",
    "you",
}


def _stem(token: str) -> str:
    if token.endswith("ies") and len(token) > 5:
        return token[:-3] + "y"
    if token.endswith("s") and not token.endswith("ss") and len(token) >= 4:
        return token[:-1]
    return token


def content_tokens(text: str) -> list[str]:
    return [
        _stem(token)
        for token in _TOKEN.findall(text.lower())
        if len(token) >= 3 and token not in _STOP
    ]


def expand_retrieval_query(question: str) -> str:
    """Add prospectus synonyms so MiniLM and lexical rerank can reach fee/department pages."""
    tokens = set(_TOKEN.findall(question.lower()))
    extras: list[str] = []
    for token in tokens:
        phrase = ACRONYMS.get(token)
        if phrase:
            extras.append(phrase)
    fee_intent = bool(tokens & {"fee", "fees", "tuition", "charges"})
    for triggers, expansion in INTENT_EXPANSIONS:
        if fee_intent and triggers & {"department", "departments"}:
            continue
        if tokens & triggers:
            extras.append(expansion)
    if not extras:
        return question.strip()
    return f"{question.strip()} {' '.join(extras)}"


PHRASE_BONUS = (
    "teaching departments",
    "listed below",
    "fee structure",
    "tuition",
    "academic programmes",
)


def lexical_overlap(question: str, passage: str) -> float:
    query_tokens = set(content_tokens(question))
    if not query_tokens:
        return 0.0
    passage_tokens = set(content_tokens(passage))
    overlap = len(query_tokens & passage_tokens) / len(query_tokens)
    lowered = passage.lower()
    bonus = 0.0
    for phrase in PHRASE_BONUS:
        if phrase in lowered and set(content_tokens(phrase)) & query_tokens:
            bonus += 0.15
    return min(1.0, overlap + bonus)


def is_followup_question(question: str, prior_questions: list[str]) -> bool:
    if not prior_questions:
        return False
    lowered = question.lower().strip()
    if any(lowered.startswith(prefix) for prefix in FOLLOWUP_PREFIXES):
        return True
    tokens = _TOKEN.findall(lowered)
    if any(token in FOLLOWUP_PRONOUNS for token in tokens) and len(tokens) <= 10:
        return True
    return False
