"""How sure Echo really is: one score from three independent signals.

    score = w_agent * agent_confidence + w_agreement * candidate_agreement + w_sound * sound_match

(starting weights 0.5 / 0.25 / 0.25 from the brief, kept in config.py to tune with real data).
The agent's own confidence alone is not reliable, so it only counts for half.
"""

from dataclasses import asdict, dataclass
from itertools import combinations

from app.config import get_settings
from app.text import similarity

# A sound match whose sentence is at least this close to the final sentence counts as "this meaning".
SAME_MEANING = 0.9


@dataclass
class Score:
    score: float
    agent_confidence: float
    candidate_agreement: float
    sound_match: float

    def as_dict(self) -> dict:
        return asdict(self)


def candidate_agreement(candidates: list[str], sentence: str) -> float:
    """0-1: how much the Whisper guesses agree with each other and with the final sentence."""
    texts = [c for c in candidates if c.strip()]
    if not texts or not sentence.strip():
        return 0.0
    # Guesses are de-duplicated before they get here, so a single guess means they all agreed.
    pairs = list(combinations(texts, 2))
    among = sum(similarity(a, b) for a, b in pairs) / len(pairs) if pairs else 1.0
    with_final = sum(similarity(c, sentence) for c in texts) / len(texts)
    return (among + with_final) / 2


def sound_match_similarity(matches: list[tuple[str, float]], sentence: str) -> float:
    """0-1: how much the recording sounds like an earlier recording that meant this sentence."""
    best = 0.0
    for text, score in matches:
        closeness = similarity(text, sentence)
        weight = 1.0 if closeness >= SAME_MEANING else closeness
        best = max(best, score * weight)
    return best


def combined_score(agent_confidence: float, candidates: list[str], sentence: str, matches: list[tuple[str, float]]) -> Score:
    s = get_settings()
    agreement = candidate_agreement(candidates, sentence)
    sound = sound_match_similarity(matches, sentence)
    total = s.score_weight_agent * agent_confidence + s.score_weight_agreement * agreement + s.score_weight_sound * sound
    return Score(
        score=round(min(1.0, max(0.0, total)), 4),
        agent_confidence=round(agent_confidence, 4),
        candidate_agreement=round(agreement, 4),
        sound_match=round(sound, 4),
    )
