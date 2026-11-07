"""Small text helpers shared by recognition, scoring and memory."""

import re
import unicodedata
from difflib import SequenceMatcher

_PUNCT = re.compile(r"[^\w\s']", re.UNICODE)
_SPACES = re.compile(r"\s+")


def normalize(text: str) -> str:
    """Lower-case, no punctuation, single spaces. Keeps Turkish letters (ş, ğ, ı, ö, ü, ç).

    casefold() turns "İ" into "i" + a combining dot, which we drop so "İstanbul" == "istanbul".
    """
    text = unicodedata.normalize("NFC", text).casefold().replace("̇", "")
    text = _PUNCT.sub(" ", text)
    return _SPACES.sub(" ", text).strip()


def similarity(a: str, b: str) -> float:
    """0-1 text similarity of two sentences after normalizing (1 = identical)."""
    na, nb = normalize(a), normalize(b)
    if not na and not nb:
        return 1.0
    if not na or not nb:
        return 0.0
    return SequenceMatcher(None, na, nb).ratio()


def word_error_rate(reference: str, hypothesis: str) -> float:
    """Word error rate: (substitutions + deletions + insertions) / words in the reference."""
    ref, hyp = normalize(reference).split(), normalize(hypothesis).split()
    if not ref:
        return 0.0 if not hyp else 1.0
    prev = list(range(len(hyp) + 1))
    for i, r in enumerate(ref, 1):
        cur = [i] + [0] * len(hyp)
        for j, h in enumerate(hyp, 1):
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (r != h))
        prev = cur
    return prev[-1] / len(ref)
