"""work-digest 공용 상수 + 유틸리티.

session_logger.py, daily_digest.py, weekly_digest.py에서 공유.
stdlib만 사용 (외부 패키지 금지).
"""

import urllib.request
import urllib.parse
from pathlib import Path

# ── 경로 ──────────────────────────────────────────

BASE_DIR = Path(__file__).resolve().parent.parent
TELEGRAM_CONF = BASE_DIR / "telegram.conf"

# ── 상수 ──────────────────────────────────────────

WEEKDAYS_KO = ["월", "화", "수", "목", "금", "토", "일"]
WORK_TAGS = ["코딩", "디버깅", "리서치", "리뷰", "ops", "설정", "문서", "설계", "리팩토링", "기타"]
WORK_TAGS_SET = set(WORK_TAGS)

# ── 유틸리티 ──────────────────────────────────────


def format_tokens(n: int, suffix: str = "") -> str:
    """Format token count: 1234 → '1.2K', 1234567 → '1.2M'.

    suffix: 붙일 접미사 (예: ' tokens')
    """
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M{suffix}"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K{suffix}"
    return f"{n}{suffix}"


def load_telegram_conf() -> dict:
    """telegram.conf에서 key=value 파싱."""
    conf = {}
    try:
        for line in TELEGRAM_CONF.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                k, v = line.split("=", 1)
                conf[k.strip()] = v.strip()
    except FileNotFoundError:
        pass
    return conf


def send_telegram(message: str, chat_id_key: str = "CHAT_ID", silent: bool = False) -> bool:
    """텔레그램 메시지 전송. 성공 시 True.

    chat_id_key: telegram.conf에서 읽을 chat_id 키 (fallback: CHAT_ID)
    silent: True면 실패해도 예외 없이 False 반환
    """
    conf = load_telegram_conf()
    bot_token = conf.get("BOT_TOKEN", "")
    chat_id = conf.get(chat_id_key) or conf.get("CHAT_ID", "")
    if not bot_token or not chat_id:
        return False

    payload = {"chat_id": chat_id, "text": message}
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{bot_token}/sendMessage",
        data=urllib.parse.urlencode(payload).encode("utf-8"),
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            import json
            result = json.loads(resp.read().decode("utf-8"))
            return result.get("ok", False)
    except Exception:
        if not silent:
            raise
        return False
