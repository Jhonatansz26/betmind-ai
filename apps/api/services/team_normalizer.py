"""
Team name normalization — canonicalizes team names for cross-provider matching.

Removes accents, lowercases, strips common suffixes (FC, SC, CD, AC, etc.)
and special characters that differ between data sources (API-Football,
football-data.org, ESPN Scoreboard).
"""
import re
import unicodedata


_SUFFIX_PATTERN = re.compile(
    r'\b(fc|sc|cf|ac|cd|sa|de|ss|if|bk|ff|fk|ca|rc|cc|ud|sd)\b',
    re.IGNORECASE,
)
_PUNCT_PATTERN = re.compile(r'[^a-z0-9\s]')
_SPACES_PATTERN = re.compile(r'\s+')


def canonical_team_name(name: str) -> str:
    """
    Normalizes a team name for cross-provider matching.

    Transformations (in order):
    1. NFKD decomposition (separates base chars from diacritics)
    2. Remove combining diacritical marks (accents, tildes)
    3. Lowercase
    4. Remove common suffixes: FC, SC, CF, AC, CD, SA, etc.
    5. Remove remaining punctuation
    6. Collapse multiple spaces → single space, trim

    Examples:
        "Atlético Tucumán" → "atletico tucuman"
        "Liverpool FC"     → "liverpool"
        "Arsenal FC"       → "arsenal"
        "Brighton & Hove Albion FC" → "brighton hove albion"
        "SE Palmeiras"     → "se palmeiras"
        "Internacional de Bogotá" → "internacional de bogota"
    """
    name = unicodedata.normalize('NFKD', name)
    name = ''.join(c for c in name if not unicodedata.combining(c))
    name = name.lower()
    name = _SUFFIX_PATTERN.sub('', name)
    name = _PUNCT_PATTERN.sub('', name)
    name = _SPACES_PATTERN.sub(' ', name).strip()
    return name
