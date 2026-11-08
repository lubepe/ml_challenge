"""Text processing shared by queries and products, so that both are tokenized the same way."""

import re
import unicodedata

# A token is a run of lowercase ASCII letters or digits. Everything else separates tokens,
# so '36"' and "36 ''" both give "36", and "72.5" gives "72" and "5".
TOKEN_PATTERN = re.compile(r"[a-z0-9]+")


def strip_accents(text: str) -> str:
    """Remove diacritics, so that ``décor`` and ``decor`` become the same word."""
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def tokenize(text: str | None) -> list[str]:
    """Return the tokens of ``text`` in order, keeping repetitions (BM25 counts them).

    Removes accents, lowercases and splits on anything that is not a letter or digit.
    No stemming and no stopword removal. Missing text gives no tokens.
    """
    if not isinstance(text, str):
        return []
    return TOKEN_PATTERN.findall(strip_accents(text).lower())
