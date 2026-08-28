"""Claim matching with polarity-aware source checks.

The public claim categories in :mod:`core.copy` remain the single term source
for audit UI.  These helpers deliberately distinguish an affirmative claim
from a seller saying that an attribute does *not* apply.
"""

from __future__ import annotations

import re

from .copy import CLAIM_CATEGORIES

NEGATION_WORDS = frozenset(
    {
        "ain't",
        "aint",
        "aren't",
        "arent",
        "can't",
        "cannot",
        "cant",
        "didn't",
        "didnt",
        "doesn't",
        "doesnt",
        "don't",
        "dont",
        "isn't",
        "isnt",
        "neither",
        "never",
        "no",
        "non",
        "nor",
        "not",
        "wasn't",
        "wasnt",
        "weren't",
        "werent",
        "without",
        "won't",
        "wont",
    }
)
NEGATION_EXCEPTIONS = frozenset({"just", "merely", "only"})


def claim_terms() -> list[tuple[str, str]]:
    """Return configured terms paired with their category, longest first."""

    terms: list[tuple[str, str]] = []
    for category, examples in CLAIM_CATEGORIES:
        cleaned = examples.replace(", and similar substances", "")
        terms.extend((category, term.strip()) for term in cleaned.split(",") if term.strip())
    return sorted(terms, key=lambda item: len(item[1]), reverse=True)


def term_present_affirmatively(text: str, term: str) -> bool:
    """Whether ``term`` occurs outside a local negative statement."""

    value = str(text or "")
    pattern = re.compile(rf"(?<!\w){re.escape(term)}(?!\w)", flags=re.IGNORECASE)
    for match in pattern.finditer(value):
        prefix = value[max(0, match.start() - 120) : match.start()].lower()
        clause_prefix = re.split(r"[\n.!?;,:]", prefix)[-1]
        words = re.findall(r"[a-z]+(?:'[a-z]+)?", clause_prefix)[-6:]
        negated = any(
            word in NEGATION_WORDS
            and not (words[index + 1 : index + 2] and words[index + 1] in NEGATION_EXCEPTIONS)
            for index, word in enumerate(words)
        )
        suffix = value[match.end() : match.end() + 24].lower()
        if re.match(r"^\s*(?:(?:[:=\-–—])\s*|\(\s*)?(?:false|no|none|not|0)\b", suffix):
            negated = True
        if not negated:
            return True
    return False


def audit_unverified_claims(
    listing_text: str, verified_source_text: str = ""
) -> list[dict[str, str]]:
    """Find affirmative configured listing claims not affirmatively present in source."""

    matches: list[dict[str, str | int]] = []
    seen: set[tuple[str, str]] = set()
    listing = str(listing_text or "")
    source = str(verified_source_text or "")
    for category, phrase in claim_terms():
        if term_present_affirmatively(source, phrase):
            continue
        pattern = re.compile(rf"(?<!\w){re.escape(phrase)}(?!\w)", re.IGNORECASE)
        for match in pattern.finditer(listing):
            # Check the enclosing clause so a preceding "not" remains visible.
            clause_start = max(listing.rfind(mark, 0, match.start()) for mark in "\n.!?;,:") + 1
            clause_endings = [listing.find(mark, match.end()) for mark in "\n.!?;,:"]
            clause_end = min((end for end in clause_endings if end >= 0), default=len(listing))
            if not term_present_affirmatively(listing[clause_start:clause_end], phrase):
                continue
            key = (category, match.group(0).casefold())
            if key not in seen:
                seen.add(key)
                matches.append(
                    {"phrase": match.group(0), "category": category, "position": match.start()}
                )
    matches.sort(key=lambda item: (int(item["position"]), str(item["category"])))
    return [{"phrase": str(item["phrase"]), "category": str(item["category"])} for item in matches]
