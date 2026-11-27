"""Keyword matching helpers shared by the rule-based agents."""
from __future__ import annotations

import re


def has_word(text: str, word: str) -> bool:
    """Return True when `word` occurs in `text`.

    Latin keywords must match whole words ("api" must not match "rapid", "hack" must not
    match "hackathon"). Arabic keywords keep substring matching because Arabic words carry
    attached prefixes and suffixes, so word boundaries are not reliable there.
    Both inputs are expected to be normalized/lower-cased by the caller.
    """
    if word.isascii():
        return re.search(rf"(?<![a-z0-9]){re.escape(word)}(?![a-z0-9])", text) is not None
    return word in text
