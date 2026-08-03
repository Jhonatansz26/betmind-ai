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

# Abreviaciones a nivel de token: ESPN usa "Independ. Rivadavia" mientras
# API-Football usa "Independiente Rivadavia". Expansión token a token para que
# ambas variantes colapsen al mismo canónico.
_TOKEN_ABBREVIATIONS: dict[str, str] = {
    "independ": "independiente",
    "indep": "independiente",
    "jrs": "juniors",
    "sde": "santiago del estero",
    "cba": "cordoba",
    "lp": "la plata",
    "acc": "asociacion atletica",
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


# Sufijos ORGANIZATIVOS inequívocamente genéricos (idioma extranjero o societario).
# Se eliminan incluso en la clave de identidad conservadora porque NUNCA
# distinguen clubes en el mismo contexto (FC, CF, IF, FF, BK, AIF, SA, FK,
# EC=Esporte Clube, CR=Clube de Regatas, SE=Sociedade Esportiva, FR=Futebol
# e Regatas, FBC=Futebol Clube, FBPA=Futebol e Regatas Porto Alegrense).
# NOTA: "sc", "cd", "ac", "rc", "ca", "ud", "club", "atletico", "real",
# "deportivo" NO se eliminan en la identidad porque pueden ser parte del
# nombre distintivo del club (ej. Barcelona SC (ECU) vs Barcelona (ESP);
# Real Madrid vs Atletico Madrid).
_IDENTITY_SUFFIX_PATTERN = re.compile(
    r'\b(fc|cf|if|ff|bk|aif|sa|fk|ec|cr|se|fr|fbc|fbpa|fcr)\b',
    re.IGNORECASE,
)

# Prefijos organizativos inequívocos que se eliminan en la identidad
# (AFC = Association Football Club). "real"/"atletico"/"club"/"deportivo"
# NO se eliminan (son distintivos).
_IDENTITY_PREFIX_PATTERN = re.compile(
    r'\b(afc)\b',
    re.IGNORECASE,
)


def team_identity_key(name: str) -> str:
    """
    Clave de identidad CONSERVADORA para detectar duplicados en la tabla
    `teams` sin fusionar clubes distintos:

    - Misma normalización base que canonical_team_name (tildes, mayúsculas,
      puntuación, abreviaciones, alias).
    - NO elimina prefijos distintivos ("real", "atletico", "club", "deportivo")
      ni sufijos potencialmente distintivos ("sc", "cd", "ac", "rc", "ec").
    - Solo elimina sufijos organizativos inequívocos (fc, cf, if, ff, bk,
      aif, sa, fk).

    Resultado: "Real Madrid" ≠ "Atletico Madrid", "Barcelona" ≠ "Barcelona SC",
    pero "Arsenal" == "Arsenal FC" y "Independ. Rivadavia" == "Independiente Rivadavia".
    """
    name = unicodedata.normalize('NFKD', name)
    name = ''.join(c for c in name if not unicodedata.combining(c))
    name = name.lower()

    alias = TEAM_NAME_ALIASES.get(name)
    if alias:
        name = alias

    name = _PUNCT_PATTERN.sub('', name)
    name = _expand_token_abbreviations(name)
    name = _IDENTITY_PREFIX_PATTERN.sub('', name)
    name = _IDENTITY_SUFFIX_PATTERN.sub('', name)
    name = _SPACES_PATTERN.sub(' ', name).strip()

    alias_clean = TEAM_NAME_ALIASES.get(name)
    if alias_clean:
        name = alias_clean

    return name


def _expand_token_abbreviations(name: str) -> str:
    """Expande abreviaciones token a token (ej: 'independ' → 'independiente')."""
    tokens = name.split()
    expanded = []
    for token in tokens:
        token = _TOKEN_ABBREVIATIONS.get(token, token)
        expanded.extend(token.split())
    return " ".join(expanded)


def canonical_team_name(name: str) -> str:
    """
    Normalizes a team name for cross-provider matching.

    Transformations (in order):
    1. NFKD decomposition (separates base chars from diacritics)
    2. Remove combining diacritical marks (accents, tildes)
    3. Lowercase
    4. Check alias dictionary for known name variants
    5. Expand token-level abbreviations (Independ. → Independiente, Jrs → Juniors)
    6. Remove common prefixes: Atlético, Club, CD, SD, CA, Real, CF, etc.
    7. Remove common suffixes: FC, SC, CF, AC, CD, SA, S.A., etc.
    8. Remove remaining punctuation
    9. Collapse multiple spaces → single space, trim
    """
    name = unicodedata.normalize('NFKD', name)
    name = ''.join(c for c in name if not unicodedata.combining(c))
    name = name.lower()

    alias = TEAM_NAME_ALIASES.get(name)
    if alias:
        name = alias

    # Quitar puntuación ANTES de expandir abreviaciones para que
    # "Independ." colapse al token "independ" y luego a "independiente".
    name = _PUNCT_PATTERN.sub('', name)
    name = _expand_token_abbreviations(name)
    name = _strip_prefixes(name)
    name = _SUFFIX_PATTERN.sub('', name)
    name = _SPACES_PATTERN.sub(' ', name).strip()

    alias_clean = TEAM_NAME_ALIASES.get(name)
    if alias_clean:
        name = alias_clean

    return name


def team_name_similarity(name_a: str, name_b: str) -> float:
    """
    Similitud Jaccard entre dos nombres de equipo canonicalizados (0.0 - 1.0).

    Considera intersección de tokens no-stop sobre unión, ponderando:
    - Match exacto → 1.0
    - Un nombre es subconjunto del otro (ej. 'central cordoba santiago'
      vs 'central cordoba santiago del estero') → proporción de tokens
      compartidos sobre el mayor conjunto.
    """
    norm_a = canonical_team_name(name_a)
    norm_b = canonical_team_name(name_b)
    if not norm_a or not norm_b:
        return 0.0
    if norm_a == norm_b:
        return 1.0

    tokens_a = set(norm_a.split()) - _STOP_WORDS
    tokens_b = set(norm_b.split()) - _STOP_WORDS
    if not tokens_a or not tokens_b:
        return 0.0

    intersection = tokens_a & tokens_b
    union = tokens_a | tokens_b
    jaccard = len(intersection) / len(union)

    # Si uno es subconjunto casi total del otro, elevar la similitud:
    # ej: {central cordoba santiago} ⊂ {central cordoba santiago del estero}
    if tokens_a <= tokens_b or tokens_b <= tokens_a:
        coverage = len(intersection) / min(len(tokens_a), len(tokens_b))
        jaccard = max(jaccard, coverage * 0.9)

    return jaccard


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
