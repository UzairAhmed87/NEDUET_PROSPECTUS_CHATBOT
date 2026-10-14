"""Checks that figures stated in an answer appear verbatim in the passages it cites."""

from __future__ import annotations

import re

_PAGE_REFERENCE = re.compile(r"\b(?:pages?|p\.)\s*\d+(?:\s*(?:,|and|-|–|to)\s*\d+)*", re.IGNORECASE)
_NUMBER = re.compile(r"(?<![\w.])\d[\d,]*(?:\.\d+)?%?")
_THOUSANDS = re.compile(r"(?<=\d),(?=\d{3})")


def _normalize(text: str) -> str:
    return _THOUSANDS.sub("", text)


def numeric_claims(text: str) -> list[str]:
    """Amounts, percentages, decimals and numbers of 3+ digits, excluding page references."""
    stripped = _PAGE_REFERENCE.sub(" ", text)
    claims: list[str] = []
    for match in _NUMBER.finditer(stripped):
        token = _normalize(match.group(0)).rstrip(".,")
        digits = token.rstrip("%")
        if not digits:
            continue
        if token.endswith("%") or "." in digits or len(digits) >= 3:
            if token not in claims:
                claims.append(token)
    return claims


def _present(claim: str, evidence: str) -> bool:
    return re.search(rf"(?<![\d.]){re.escape(claim)}(?![\d])", evidence) is not None


def unsupported_claims(answer: str, evidence_texts: list[str], *, question: str = "") -> list[str]:
    evidence = _normalize(" ".join(evidence_texts))
    asked = set(numeric_claims(question))
    return [claim for claim in numeric_claims(answer) if claim not in asked and not _present(claim, evidence)]
