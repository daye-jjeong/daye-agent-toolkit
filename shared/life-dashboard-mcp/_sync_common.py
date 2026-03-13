"""Shared helpers for sync_cc / sync_codex."""

import re

# Keyword-based auto-tagging when work-log tag is unavailable.
# Order matters: first match wins.
TAG_KEYWORDS: list[tuple[str, list[str]]] = [
    ("디버깅", ["debug", "디버깅", "에러", "error", "fix", "버그", "traceback", "stack trace",
               "동작 안", "동작안해", "왜 안"]),
    ("리뷰", ["review", "리뷰", "code quality", "pr review", "approved", "rejected",
             "git diff", "검토", "괜찮은지", "수정할건"]),
    ("리서치", ["리서치", "research", "조사", "비교", "추천", "어떤게 있을까", "프레임워크"]),
    ("설계", ["설계", "design", "기획", "plan", "아키텍처", "brainstorm",
             "목업", "mockup", "mock-up", "검증", "verify"]),
    ("설정", ["설정", "config", "setup", "셋업", "install", "init"]),
    ("문서", ["문서", "SKILL.md", "README", "documentation", "표준화", "문서화"]),
    ("리팩토링", ["리팩토링", "refactor", "정리", "통합", "consolidat"]),
    ("ops", ["deploy", "배포", "cron", "monitor", "운영", "워치독",
            "thread list", "task list", "minions"]),
    ("코딩", ["구현", "implement", "추가", "생성", "만들", "작성", "feature",
             "write_file", "apply_diff", "create_file"]),
]

# Short English keywords that must match as whole words (not inside identifiers).
# e.g. "error" should not match "ingredient_weight_error".
_WORD_BOUNDARY_KW = frozenset({"error", "fix", "init", "plan"})


def _kw_matches(kw: str, text: str) -> bool:
    kw_lower = kw.lower()
    if kw_lower in _WORD_BOUNDARY_KW:
        return bool(re.search(r"\b" + re.escape(kw_lower) + r"\b", text))
    return kw_lower in text


def auto_tag(*text_sources: str) -> str:
    """Infer work tag from text content. Pass summary, topic, commands, etc."""
    text = " ".join(text_sources).lower()
    for tag, keywords in TAG_KEYWORDS:
        if any(_kw_matches(kw, text) for kw in keywords):
            return tag
    return "기타"
