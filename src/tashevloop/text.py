from __future__ import annotations

import re

STOP = {
    "the","a","an","and","or","to","of","in","on","for","with","from","by","is","are",
    "это","как","что","и","или","на","в","во","для","с","со","из","по","не","при","у"
}


# Commit trailers and tool footers carry attribution, not guidance.
TRAILER_LINE = re.compile(
    r"^\s*(?:(?:co-authored|signed-off|reviewed|acked|tested|reported|suggested|helped)-by"
    r"|change-id)\s*:.*$"
    r"|^\s*🤖 generated with .*$",
    re.IGNORECASE | re.MULTILINE,
)


def strip_trailers(text: str) -> str:
    """Remove commit trailers such as Co-Authored-By: and tool footers."""
    return TRAILER_LINE.sub("", text).strip()


def tokens(text: str) -> list[str]:
    words = re.findall(r"[a-zA-Zа-яА-ЯёЁ0-9_\-]{2,}", text.lower())
    return [w for w in words if w not in STOP]


def signature(title: str, description: str = "", tags: list[str] | None = None) -> str:
    pool = tokens(f"{title} {description}")
    if tags:
        pool.extend(tags)
    uniq: list[str] = []
    seen: set[str] = set()
    for word in pool:
        if word not in seen:
            seen.add(word)
            uniq.append(word)
    return "|".join(sorted(uniq[:8])) or "general"


def overlap_score(query: str, signature_text: str, tags: list[str]) -> float:
    q = set(tokens(query))
    s = set(signature_text.split("|")) | set(tags)
    if not q or not s:
        return 0.0
    return len(q & s) / max(1, len(q | s))
