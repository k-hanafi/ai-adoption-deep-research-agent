"""Chrome-strip, claim windows, and anchor helpers for citation verification."""

from __future__ import annotations

import re
from typing import Optional, Sequence
from urllib.parse import urlparse

from citation_verification import config

_CHROME_LINE = re.compile(
    r"("
    r"^(div|span|nav|footer|header|section|aside)\s*$"
    r"|related (posts?|resources?|articles?|content)"
    r"|skip to (main )?content"
    r"|subscribe( to (our )?(newsletter|updates?))?"
    r"|cookie(s)? (policy|settings|consent|notice|banner)"
    r"|accept (all )?cookies"
    r"|we use cookies"
    r"|sign up for"
    r")",
    re.IGNORECASE,
)
_LEADING_TAG = re.compile(r"^(</?[a-zA-Z][^>]*>\s*)+")
_BLANK_RUN = re.compile(r"\n{3,}")
_QUOTE = re.compile(r"\"([^\"]{3,80})\"|“([^”]{3,80})”")
_PROPER = re.compile(r"\b([A-Z][a-zA-Z0-9]+(?:\s+[A-Z][a-zA-Z0-9]+){0,3})\b")
_TOKEN = re.compile(r"[A-Za-z][A-Za-z0-9.+#-]{2,}")
_STOP = frozenset(
    {
        "the",
        "and",
        "for",
        "with",
        "uses",
        "used",
        "use",
        "using",
        "their",
        "this",
        "that",
        "from",
        "into",
        "about",
        "after",
        "before",
        "company",
        "says",
        "said",
        "writes",
        "write",
        "article",
        "page",
        "blog",
        "team",
        "internal",
        "across",
        "every",
        "most",
        "all",
        "its",
        "our",
        "has",
        "have",
        "been",
        "were",
        "was",
        "are",
        "not",
        "but",
        "than",
        "then",
        "when",
        "who",
        "what",
        "how",
        "why",
        "can",
        "will",
        "also",
        "more",
        "only",
        "just",
        "very",
        "over",
        "under",
        "into",
        "onto",
        "via",
        "per",
        "each",
        "both",
        "such",
        "including",
        "includes",
        "description",
        "founder",
        "ceo",
        "author",
        "hosted",
        "company-hosted",
        "constantly",
        "asking",
        "questions",
        "receiving",
        "answers",
        "plain-language",
        "window",
        "chat",
    }
)
_PARKED_HOSTS = frozenset({"example.com", "example.org", "example.net"})
_SOFT_404 = re.compile(
    r"\b(page not found|404 not found|this page (does not|doesn't) exist|"
    r"we couldn't find|content isn't available)\b",
    re.IGNORECASE,
)
_POISON_MOT = re.compile(
    r"\b(mot status|vehicle mot|road safety standards)\b",
    re.IGNORECASE,
)


def strip_chrome(text: str) -> str:
    """Drop leftover tags, skip-nav, and related-resource chrome."""
    raw = (text or "").replace("\r\n", "\n")
    raw = _LEADING_TAG.sub("", raw.strip())
    kept: list[str] = []
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped:
            kept.append("")
            continue
        if _CHROME_LINE.search(stripped) and len(stripped) < 80:
            continue
        kept.append(line.rstrip())
    body = "\n".join(kept)
    body = _BLANK_RUN.sub("\n\n", body).strip()
    return body


def cap_snippet(text: str, *, limit: int = config.MAX_SNIPPET_CHARS) -> tuple[str, bool]:
    """Truncate after strip. Returns (text, truncated)."""
    cleaned = strip_chrome(text)
    if len(cleaned) > limit:
        return cleaned[:limit], True
    return cleaned, False


def chunk_text(
    text: str,
    *,
    size: int = config.CHUNK_CHARS,
    overlap: int = config.CHUNK_OVERLAP,
) -> list[str]:
    """Overlapping windows over the kept page text."""
    body = (text or "").strip()
    if not body:
        return []
    if len(body) <= size:
        return [body]
    step = max(1, size - overlap)
    windows: list[str] = []
    start = 0
    while start < len(body):
        windows.append(body[start : start + size])
        if start + size >= len(body):
            break
        start += step
    return windows


def extract_anchors(claim: str) -> list[str]:
    """Distinctive quote / person / company / tool tokens from the claim."""
    text = (claim or "").strip()
    if not text:
        return []
    found: list[str] = []
    seen: set[str] = set()

    def _add(value: str) -> None:
        token = value.strip()
        if len(token) < 3:
            return
        key = token.lower()
        if key in seen or key in _STOP:
            return
        seen.add(key)
        found.append(token)

    for match in _QUOTE.finditer(text):
        _add(next(group for group in match.groups() if group))
    for match in _PROPER.finditer(text):
        phrase = match.group(1)
        parts = phrase.split()
        if parts and parts[0].lower() in _STOP:
            parts = parts[1:]
        if parts:
            _add(" ".join(parts))
    for match in _TOKEN.finditer(text):
        token = match.group(0)
        if token.lower() in _STOP:
            continue
        if token[0].isupper() and len(token) >= 4:
            _add(token)
    if not found:
        for match in _TOKEN.finditer(text):
            token = match.group(0)
            if token.lower() not in _STOP and len(token) >= 6:
                _add(token)
    return found


def missing_anchors(text: str, anchors: Sequence[str]) -> list[str]:
    """Anchors that do not appear in the kept text (case-insensitive)."""
    hay = (text or "").lower()
    return [anchor for anchor in anchors if anchor.lower() not in hay]


def select_windows(text: str, claim: str) -> list[str]:
    """Windows to judge: every anchor hit, else every chunk on the page.

    When claim names never appear, a later paraphrase or role stand-in
    still has to reach the judge. Do not keep only the first chunk.
    """
    anchors = extract_anchors(claim)
    windows = chunk_text(text)
    if not windows:
        return []
    if not anchors:
        return windows
    hits = [
        window
        for window in windows
        if any(anchor.lower() in window.lower() for anchor in anchors)
    ]
    if hits:
        return hits
    return windows


def combine_chunk_verdicts(
    verdicts: Sequence[Optional[int]],
) -> tuple[Optional[int], Optional[str]]:
    """Merge per-window 0/1 into one package verdict.

    Any 1 wins. All judged 0s stay 0. Missing exact strings do not
    veto. Null only when no window produced a 0/1.
    """
    if any(value == 1 for value in verdicts):
        return 1, None
    judged = [value for value in verdicts if value in (0, 1)]
    if judged and all(value == 0 for value in judged):
        return 0, None
    return None, "judge produced no usable window"


def looks_document_mismatch(url: str, title: str, snippet: str) -> bool:
    """Cheap identity clash (parked host labeled on the wrong body)."""
    host = _host(url)
    blob = f"{title}\n{snippet}"
    if host in _PARKED_HOSTS:
        lowered = blob.lower()
        if "example domain" in lowered or "iana.org" in lowered:
            return False
        if _POISON_MOT.search(blob):
            return True
        words = [part for part in (title or "").split() if part]
        if len(words) >= 4 and "example" not in title.lower():
            return True
    return False


def looks_soft_404(snippet: str) -> bool:
    text = (snippet or "").strip()
    if not text:
        return False
    if _SOFT_404.search(text) and len(text) < 800:
        return True
    return False


def documents_disagree(
    title_a: str,
    snippet_a: str,
    title_b: str,
    snippet_b: str,
) -> bool:
    """True when two vendors clearly returned different documents."""
    ta = (title_a or "").strip().lower()
    tb = (title_b or "").strip().lower()
    if ta and tb and ta != tb:
        words_a = set(_TOKEN.findall(snippet_a.lower()))
        words_b = set(_TOKEN.findall(snippet_b.lower()))
        if not words_a or not words_b:
            return True
        overlap = len(words_a & words_b) / max(1, len(words_a | words_b))
        return overlap < 0.12
    return False


def _host(url: str) -> str:
    host = (urlparse(url).hostname or "").lower()
    if host.startswith("www."):
        return host[4:]
    return host
