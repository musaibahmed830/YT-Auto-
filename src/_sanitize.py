"""
Shared sanitization for secrets/credentials and free-text content that flow
into HTTP requests. Every API key/token used anywhere in this pipeline should
be passed through sanitize_credential() before use.

Why this exists: values copy-pasted through chat UIs, PDFs, or some browsers
can pick up invisible Unicode (zero-width spaces, U+2028/U+2029 line/paragraph
separators, stray control characters). Python's stdlib HTTP clients encode
header values as ASCII or latin-1 and raise UnicodeEncodeError on these
characters instead of stripping them, which crashes the whole pipeline run.
"""

import unicodedata

# Unicode categories to strip from free text: Cc/Cf (control/format chars)
# and Zl/Zp (line/paragraph separators, e.g. U+2028, U+2029).
_STRIP_CATEGORIES = ("Cc", "Cf", "Zl", "Zp")


def sanitize_text(text: str) -> str:
    """For narration/body content: strip invisible junk but keep newlines/tabs."""
    return "".join(
        c for c in text
        if c in "\n\t" or unicodedata.category(c) not in _STRIP_CATEGORIES
    )


def sanitize_credential(value: str) -> str:
    """For API keys/tokens/IDs that go into HTTP headers: strip ALL whitespace
    and control/format/separator characters, since credentials should never
    legitimately contain any of them."""
    return "".join(c for c in value if c.isprintable() and c not in " \t").strip()
