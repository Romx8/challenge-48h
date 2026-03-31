import re
import unicodedata


def normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_only = normalized.encode("ascii", "ignore").decode("ascii")
    ascii_only = ascii_only.strip().lower()
    ascii_only = re.sub(r"[^a-z0-9]+", "_", ascii_only)
    return ascii_only.strip("_")
