"""
Team name normalization — canonicalizes team names for cross-provider matching.

Removes accents, lowercases, strips common suffixes and prefixes (FC, SC, CD, AC,
Atlético, Club, Deportivo, etc.) and special characters that differ between data
sources (API-Football, football-data.org, ESPN Scoreboard).

Also includes fuzzy matching fallback for partial matches.
"""
import re
import unicodedata
from typing import Optional

_PREFIX_PATTERN = re.compile(
    r'\b(atletico|atlético|club|cd|deportivo|sd|ca|real|cf|sc|fc|ac|rc|ud|ss|if|bk|ff|fk|cc|sa)\b',
    re.IGNORECASE,
)
_SUFFIX_PATTERN = re.compile(
    r'\b(fc|sc|cf|ac|cd|sa|de|ss|if|bk|ff|fk|ca|rc|cc|ud|sd|s\.a\.?|s a|spa|srl)\b',
    re.IGNORECASE,
)
_PUNCT_PATTERN = re.compile(r'[^a-z0-9\s]')
_SPACES_PATTERN = re.compile(r'\s+')

_STOP_WORDS: set[str] = {
    "los", "las", "el", "la", "de", "del", "y", "e", "o", "a",
    "the", "of", "and", "in", "fc", "sc", "cf", "ac", "cd",
}

TEAM_NAME_ALIASES: dict[str, str] = {
    "junior": "atletico junior",
    "atletico junior": "junior",
    "nacional": "atletico nacional",
    "atletico nacional": "nacional",
    "millonarios": "millonarios fc",
    "santa fe": "independiente santa fe",
    "independiente santa fe": "santa fe",
    "inter palmira": "internacional palmira",
    "internacional palmira": "inter palmira",
    "boca": "boca juniors",
    "boca jrs": "boca juniors",
    "river": "river plate",
    "racing": "racing club",
    "racing club": "racing",
    "velez": "velez sarsfield",
    "huracan": "huracan",
    "gimnasia": "gimnasia la plata",
    "gimnasia lp": "gimnasia la plata",
    "independiente": "independiente",
    "estudiantes": "estudiantes de la plata",
    "estudiantes lp": "estudiantes de la plata",
    "talleres": "talleres cordoba",
    "talleres cba": "talleres cordoba",
    "instituto": "instituto cordoba",
    "instituto acc": "instituto cordoba",
    "newells": "newells old boys",
    "central": "rosario central",
    "lanus": "lanus",
    "belgrano": "belgrano",
    "tigre": "tigre",
    "aldosivi": "aldosivi",
    "sarmiento": "sarmiento",
    "union": "union santa fe",
    "san lorenzo": "san lorenzo",
    "defensa": "defensa y justicia",
    "def y justicia": "defensa y justicia",
    "barracas": "barracas central",
    "central cordoba": "central cordoba sde",
    "riestra": "deportivo riestra",
    "platense": "platense",
    "argentinos": "argentinos juniors",
    "argentinos jrs": "argentinos juniors",
}


def _strip_prefixes(name: str) -> str:
    return _PREFIX_PATTERN.sub('', name)


def canonical_team_name(name: str) -> str:
    """
    Normalizes a team name for cross-provider matching.

    Transformations (in order):
    1. NFKD decomposition (separates base chars from diacritics)
    2. Remove combining diacritical marks (accents, tildes)
    3. Lowercase
    4. Check alias dictionary for known name variants
    5. Remove common prefixes: Atlético, Club, CD, SD, CA, Real, CF, etc.
    6. Remove common suffixes: FC, SC, CF, AC, CD, SA, S.A., etc.
    7. Remove remaining punctuation
    8. Collapse multiple spaces → single space, trim
    """
    name = unicodedata.normalize('NFKD', name)
    name = ''.join(c for c in name if not unicodedata.combining(c))
    name = name.lower()

    alias = TEAM_NAME_ALIASES.get(name)
    if alias:
        name = alias

    name = _strip_prefixes(name)
    name = _SUFFIX_PATTERN.sub('', name)
    name = _PUNCT_PATTERN.sub('', name)
    name = _SPACES_PATTERN.sub(' ', name).strip()

    alias_clean = TEAM_NAME_ALIASES.get(name)
    if alias_clean:
        name = alias_clean

    return name


def fuzzy_match_team(search_name: str, candidates: list[str]) -> Optional[str]:
    """
    Tries to find a fuzzy match for search_name among candidate names.
    Returns the best matching candidate name, or None if no match found.
    """
    norm_search = canonical_team_name(search_name)
    if not norm_search:
        return None

    # Token set matching: check if all tokens of one name are in the other
    search_tokens = set(norm_search.split()) - _STOP_WORDS
    if not search_tokens:
        return None

    for candidate in candidates:
        norm_cand = canonical_team_name(candidate)
        cand_tokens = set(norm_cand.split()) - _STOP_WORDS
        if not cand_tokens:
            continue

        intersection = search_tokens & cand_tokens
        if len(intersection) == 0:
            continue

        overlap_ratio = len(intersection) / max(len(search_tokens), len(cand_tokens))
        if overlap_ratio >= 0.6:
            return candidate

    for candidate in candidates:
        norm_cand = canonical_team_name(candidate)
        cand_tokens = set(norm_cand.split()) - _STOP_WORDS
        if not cand_tokens:
            continue

        intersection = search_tokens & cand_tokens
        if len(intersection) > 0:
            overlap_smaller = len(intersection) / min(len(search_tokens), len(cand_tokens))
            if overlap_smaller >= 0.75:
                return candidate

    return None
