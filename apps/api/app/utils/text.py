import re

SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")
WHITESPACE = re.compile(r"[ \t]+")


def normalize_text(value: str) -> str:
    lines = [WHITESPACE.sub(" ", line).rstrip() for line in value.replace("\r\n", "\n").split("\n")]
    collapsed = "\n".join(lines)
    collapsed = re.sub(r"\n{3,}", "\n\n", collapsed)
    return collapsed.strip()


def split_paragraphs(text: str) -> list[str]:
    parts = re.split(r"\n\s*\n", normalize_text(text))
    return [part.strip() for part in parts if part.strip()]


def split_sentences(text: str) -> list[str]:
    pieces = SENTENCE_SPLIT.split(text.strip())
    return [piece.strip() for piece in pieces if piece.strip()]


def looks_like_heading(line: str) -> bool:
    compact = line.strip()
    if not compact or len(compact) > 90:
        return False
    if compact.endswith("."):
        return False
    letters = [char for char in compact if char.isalpha()]
    if len(letters) < 4:
        return False
    uppercase_ratio = sum(1 for char in letters if char.isupper()) / len(letters)
    return uppercase_ratio >= 0.65 or compact[:1].isdigit()


def excerpt(text: str, limit: int = 280) -> str:
    compact = " ".join(text.split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 1].rstrip() + "…"
