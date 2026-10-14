"""In-memory BM25 index over stored chunks, used alongside vector search.

Exact identifiers matter in the prospectus (SF-1, CT-175, R-11(a), BS (CT), 51,930), so
tokenisation keeps letter+digit codes as single tokens and drops thousands separators.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass

from app.utils.query import _stem

_CODE = re.compile(r"\b([a-z]{1,4})\s?-\s?(\d{1,3}[a-z]?)\b")
_TOKEN = re.compile(r"[a-z0-9]+(?:\.\d+)?")

STOPWORDS = frozenset(
    {
        # English
        "the", "and", "for", "are", "was", "were", "what", "when", "which", "how", "many", "much",
        "there", "does", "about", "from", "with", "this", "that", "your", "not", "but", "you", "can",
        "will", "who", "its", "into", "any", "all", "per", "shall", "should", "have", "has", "been",
        "their", "them", "they", "his", "her", "him", "she", "may", "also", "only", "such", "other",
        "tell", "please", "is", "of", "to", "in", "on", "at", "by", "or", "an", "a", "be", "as", "if",
        "do", "i", "me", "my", "we", "it",
        # Roman Urdu function words
        "hai", "hain", "ka", "ki", "ke", "ko", "mein", "main", "kya", "kitni", "kitna", "kitne", "liye",
        "se", "aur", "ya", "agar", "kis", "ne", "kar", "karun", "karna", "hoti", "hota", "hote", "milegi",
        "milta", "milti", "andar", "bhi", "koi", "kaise", "kab", "kahan", "chahiye", "wala", "wali",
    }
)


def lexical_tokens(text: str) -> list[str]:
    lowered = re.sub(r"(?<=\d),(?=\d{3})", "", text.lower())
    tokens: list[str] = []
    for match in _CODE.finditer(lowered):
        tokens.append(f"{match.group(1)}{match.group(2)}")
    for token in _TOKEN.findall(lowered):
        if token in STOPWORDS:
            continue
        if token.isalpha():
            if len(token) < 2:
                continue
            token = _stem(token)
        tokens.append(token)
    return tokens


@dataclass
class LexicalHit:
    chunk_id: str
    score: float


class BM25Index:
    def __init__(self, k1: float = 1.5, b: float = 0.75) -> None:
        self.k1 = k1
        self.b = b
        self._ids: list[str] = []
        self._meta: list[dict] = []
        self._tf: list[Counter] = []
        self._lengths: list[int] = []
        self._df: Counter = Counter()
        self._avg_len = 0.0

    def __len__(self) -> int:
        return len(self._ids)

    def build(self, rows: list[tuple[str, str, dict]]) -> "BM25Index":
        self._ids, self._meta, self._tf, self._lengths = [], [], [], []
        self._df = Counter()
        for chunk_id, text, metadata in rows:
            counts = Counter(lexical_tokens(text))
            self._ids.append(chunk_id)
            self._meta.append(metadata or {})
            self._tf.append(counts)
            self._lengths.append(sum(counts.values()))
            self._df.update(counts.keys())
        self._avg_len = (sum(self._lengths) / len(self._lengths)) if self._lengths else 0.0
        return self

    def idf(self, token: str) -> float:
        n = len(self._ids)
        df = self._df.get(token, 0)
        return math.log(1 + (n - df + 0.5) / (df + 0.5))

    def search(
        self,
        query: str,
        *,
        top_n: int,
        document_ids: list[str] | None = None,
        academic_year: str | None = None,
    ) -> list[LexicalHit]:
        terms = list(dict.fromkeys(lexical_tokens(query)))
        if not terms or not self._ids:
            return []
        allowed_docs = set(document_ids or [])
        scored: list[LexicalHit] = []
        for index, counts in enumerate(self._tf):
            meta = self._meta[index]
            if allowed_docs and meta.get("document_id") not in allowed_docs:
                continue
            if academic_year and meta.get("academic_year") != academic_year:
                continue
            length_norm = self.k1 * (1 - self.b + self.b * self._lengths[index] / (self._avg_len or 1))
            score = 0.0
            for term in terms:
                tf = counts.get(term, 0)
                if tf:
                    score += self.idf(term) * tf * (self.k1 + 1) / (tf + length_norm)
            if score > 0:
                scored.append(LexicalHit(self._ids[index], score))
        scored.sort(key=lambda hit: hit.score, reverse=True)
        return scored[:top_n]

    def weighted_coverage(self, query: str, text: str) -> float:
        """IDF-weighted share of the query's distinct terms that occur in `text` (0..1)."""
        terms = list(dict.fromkeys(lexical_tokens(query)))
        if not terms:
            return 0.0
        present = set(lexical_tokens(text))
        weights = {term: self.idf(term) for term in terms}
        total = sum(weights.values()) or 1.0
        return sum(weight for term, weight in weights.items() if term in present) / total


def reciprocal_rank_fusion(rankings: list[list[str]], *, k: int = 60) -> list[tuple[str, float]]:
    """Standard RRF (Cormack et al., 2009): score(d) = sum over rankings of 1 / (k + rank)."""
    scores: dict[str, float] = {}
    for ranking in rankings:
        for rank, chunk_id in enumerate(ranking, start=1):
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (k + rank)
    return sorted(scores.items(), key=lambda item: item[1], reverse=True)
