import re

_UNSAFE_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_WHITESPACE = re.compile(r"\s+")


def safe_filename(name: str) -> str:
    """Sanitizes a workflow name for use as a download filename (no extension)."""
    cleaned = _UNSAFE_CHARS.sub("", name or "").strip()
    cleaned = _WHITESPACE.sub(" ", cleaned)
    return cleaned or "Documentation"
