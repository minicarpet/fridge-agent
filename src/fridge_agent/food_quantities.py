import unicodedata


_INVARIANT_WORDS = {
    "ananas",
    "couscous",
    "houmous",
    "jus",
    "mais",
    "maïs",
    "noix",
    "pois",
    "riz",
}


def normalize_food_name(
    name: str,
) -> str:
    words = (
        unicodedata.normalize(
            "NFKC",
            name,
        )
        .casefold()
        .split()
    )

    return " ".join(
        _normalize_word(word)
        for word in words
    )


def canonical_quantity(
    quantity: float,
    unit: str,
) -> tuple[float, str]:
    if unit == "kg":
        return quantity * 1000.0, "g"

    if unit == "l":
        return quantity * 1000.0, "ml"

    return quantity, unit


def from_canonical_quantity(
    quantity: float,
    original_unit: str,
) -> float:
    if original_unit == "kg":
        return quantity / 1000.0

    if original_unit == "l":
        return quantity / 1000.0

    return quantity


def _normalize_word(
    word: str,
) -> str:
    if word in _INVARIANT_WORDS:
        return word

    if len(word) <= 3:
        return word

    if word.endswith(("s", "x")):
        return word[:-1]

    return word