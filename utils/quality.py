"""Heuristics for detecting / sanitising garbage in LLM output streams
and DuckDuckGo search results.

Andre v2.3 — added after observing Kimi K2.6 occasionally drift into:
  • repetition collapse (long runs of one char, n-grams repeated 20+ times),
  • Chinese / non-Latin content when the task is English,
  • off-topic answers triggered by noisy search results.
"""
from __future__ import annotations

import re
from collections import Counter


# Strip C0/C1 controls except \t \n \r
_CONTROL_RE = re.compile(r"[\x00-\x08\x0b-\x0c\x0e-\x1f\x7f]")

# 30+ of the same non-whitespace char in a row is degenerate; collapse to 12.
_RUN_RE = re.compile(r"(\S)\1{30,}")


def detect_collapse(window: str) -> str | None:
    """Return a short reason string when ``window`` shows a repetition
    collapse. Caller should abort the LLM stream when this is non-None.

    Two checks:
      1. >=120-character run of the same non-whitespace char.
      2. A 6-character n-gram appearing 18+ times in the window.

    Trades off precision/recall in the conservative direction —
    legitimate markdown tables and ASCII rule lines (`---`) won't trip
    it because they're not 120+ chars of the same char unbroken.
    """
    if not window or len(window) < 120:
        return None

    # (1) single-char run
    prev = window[0]
    run = 1
    for i in range(1, len(window)):
        ch = window[i]
        if ch == prev and not ch.isspace():
            run += 1
            if run >= 120:
                return f"single-char run {prev!r}×{run}"
        else:
            prev = ch
            run = 1

    # (2) repeated 6-gram
    if len(window) >= 240:
        grams = [window[i:i + 6] for i in range(len(window) - 5)]
        counts = Counter(
            g for g in grams
            if len(set(g)) > 1 and not g.isspace() and any(c.isalnum() or c in "-=|*_" for c in g)
        )
        if counts:
            top, n = counts.most_common(1)[0]
            if n >= 22:
                return f"6-gram {top!r} repeated {n}×"
    return None


def sanitize_text(s: str, max_len: int = 8000) -> str:
    """Strip control chars, collapse runaway char repetitions, truncate."""
    if not s:
        return ""
    s = _CONTROL_RE.sub("", s)
    s = _RUN_RE.sub(lambda m: m.group(1) * 12, s)
    # Cap silly whitespace runs
    s = re.sub(r"\n{4,}", "\n\n\n", s)
    s = re.sub(r"[ \t]{8,}", "    ", s)
    if len(s) > max_len:
        s = s[:max_len].rsplit(" ", 1)[0] + " …"
    return s


def is_garbage_page(text: str) -> bool:
    """Return True if a fetched page looks like noise we should not feed
    to the LLM as evidence. Triggers when the text is empty, very short,
    contains a repetition collapse, or is overwhelmingly non-Latin."""
    if not text:
        return True
    if len(text) < 80:
        return True
    if detect_collapse(text[-1500:]) is not None:
        return True
    # ASCII-only Latin coverage. Python's str.isalnum() counts CJK
    # characters as alphanumeric, so we need the explicit isascii() guard.
    safe_punct = ".,;:?!()-—_'\"/[]{}#$%&*+<=>@\\^`|~"
    latin = sum(
        1 for c in text
        if (c.isascii() and c.isalnum()) or c.isspace() or c in safe_punct
    )
    # If less than ~45% of the page is recognisable Latin/printable text,
    # treat it as noise.
    if latin / len(text) < 0.45:
        return True
    return False


def latin_ratio(text: str) -> float:
    """Convenience: 0..1 ratio of ASCII-Latin/printable characters."""
    if not text:
        return 0.0
    safe_punct = ".,;:?!()-—_'\"/[]{}#$%&*+<=>@\\^`|~"
    latin = sum(
        1 for c in text
        if (c.isascii() and c.isalnum()) or c.isspace() or c in safe_punct
    )
    return latin / len(text)


# Kimi K2.6 occasionally leaks its internal chat-template control tokens
# into the visible text output, especially around the "stopThinking"
# transition. The NIM endpoint *should* consume them — when it doesn't,
# we strip them client-side.
_TOOL_BLOCK_RE = re.compile(
    r"<\|tool_calls_section_begin\|>.*?<\|tool_calls_section_end\|>",
    re.DOTALL,
)
_TOOL_CALL_BLOCK_RE = re.compile(
    r"<\|tool_call_begin\|>.*?<\|tool_call_end\|>",
    re.DOTALL,
)
# Catch leftover argument residue like `functions.stopThinking:0{"action": "..."}`
_TOOL_RESIDUE_RE = re.compile(
    r"functions\.[A-Za-z_]\w*:\d+\s*\{[^{}]*\}",
)
# Strip any orphan Kimi/ChatML-style control tokens — patterns like
# <|im_start|>, <|tool_call_begin|>, <|reserved_special_token_42|> etc.
_KIMI_TOKEN_RE = re.compile(r"<\|[A-Za-z_][\w]*(?:\|[\w]*)*\|>")


def strip_control_tokens(text: str) -> str:
    """Remove Kimi K2.6 internal control tokens from a string. Safe to
    call repeatedly and on partial / streaming chunks (orphan tokens
    are stripped even when their enclosing block didn't arrive)."""
    if not text:
        return text
    # 1. Whole tool-call sections — drop the entire block.
    text = _TOOL_BLOCK_RE.sub("", text)
    # 2. Bare tool_call blocks (sometimes appear without the section wrapper).
    text = _TOOL_CALL_BLOCK_RE.sub("", text)
    # 3. Function-call argument residue like `functions.stopThinking:0{...}`.
    text = _TOOL_RESIDUE_RE.sub("", text)
    # 4. Any orphan `<|...|>` control tokens.
    text = _KIMI_TOKEN_RE.sub("", text)
    return text


def looks_like_pure_garbage(text: str) -> bool:
    """Return True when ``text`` is essentially worthless after stripping
    control tokens — empty, too short, or majority-non-Latin. Used by
    agents to detect a failed generation and avoid cascading bad context."""
    if not text:
        return True
    stripped = strip_control_tokens(text).strip()
    if len(stripped) < 200:
        return True
    if latin_ratio(stripped) < 0.5:
        return True
    return False
    return latin / len(text)
