"""Shared constants and helpers for Codex work-digest scripts."""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
TELEGRAM_CONF = BASE_DIR / "telegram.conf"
FALLBACK_TELEGRAM_CONF = Path(__file__).resolve().parents[3] / "cc" / "work-digest" / "telegram.conf"

WEEKDAYS_KO = ["월", "화", "수", "목", "금", "토", "일"]
WORK_TAGS = ["코딩", "디버깅", "리서치", "리뷰", "ops", "설정", "문서", "설계", "리팩토링", "기타"]
WORK_TAGS_SET = set(WORK_TAGS)


def format_tokens(n: int, suffix: str = "") -> str:
    """Format token counts with compact units."""
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M{suffix}"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K{suffix}"
    return f"{n}{suffix}"


def _read_conf(path: Path) -> dict[str, str]:
    conf: dict[str, str] = {}
    if not path.exists():
        return conf
    for line in path.read_text().splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        conf[key.strip()] = value.strip()
    return conf


def load_telegram_conf() -> dict[str, str]:
    """Load Telegram config, letting Codex-local config override Claude fallback."""
    conf = _read_conf(FALLBACK_TELEGRAM_CONF)
    conf.update(_read_conf(TELEGRAM_CONF))
    return conf


def send_telegram(message: str, chat_id_key: str = "CHAT_ID", silent: bool = False) -> bool:
    """Send a Telegram message using configured bot credentials."""
    conf = load_telegram_conf()
    bot_token = conf.get("BOT_TOKEN", "")
    chat_id = conf.get(chat_id_key) or conf.get("CHAT_ID", "")
    if not bot_token or not chat_id:
        return False

    payload = {"chat_id": chat_id, "text": message}
    if silent:
        payload["disable_notification"] = "true"

    request = urllib.request.Request(
        f"https://api.telegram.org/bot{bot_token}/sendMessage",
        data=urllib.parse.urlencode(payload).encode("utf-8"),
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            result = json.loads(response.read().decode("utf-8"))
        return bool(result.get("ok"))
    except Exception:
        if not silent:
            raise
        return False
