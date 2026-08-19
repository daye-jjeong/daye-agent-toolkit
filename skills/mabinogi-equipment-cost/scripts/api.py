"""mabimobi.life 비공식 API 클라이언트.

**urllib을 쓴다. curl이나 외부 HTTP 라이브러리로 바꾸면 403으로 차단된다**
(같은 요청을 curl로 보내면 403, urllib로 보내면 200 — 실측. TLS 지문 차이로 보인다).

엔드포인트 3종:
    GET /d/api/v1/market/prices?limit=500&offset=N   시세 목록 (쿼터 없음)
    GET /d/api/v1/items?search=<말머리>&limit=200     아이템 목록 (쿼터 없음)
    GET /d/api/v1/items/<id>                          아이템 상세 (IP 단위 쿼터)
    GET /d/api/v1/market/prices/history?kind_id=&interval=  일·주·월봉 (쿼터 없음)
"""

import gzip
import json
import re
import urllib.error
import urllib.parse
import urllib.request

BASE = "https://mabimobi.life/d/api/v1"
UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
    " (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)
PRICE_PAGE = 500


class Throttled(Exception):
    """상세 API 쿼터. 남은 초를 알고 있으면 retry_after에 담는다."""

    def __init__(self, retry_after=None):
        super().__init__(f"throttled, retry after {retry_after}s")
        self.retry_after = retry_after


def parse_retry_after(body):
    """429 본문에서 남은 초를 뽑는다.

    실측 응답: {"detail": "Request was throttled. Expected available in 578 seconds."}
    """
    if isinstance(body, dict):
        body = body.get("detail", "")
    m = re.search(r"(\d+)\s*seconds?", str(body))
    return int(m.group(1)) if m else None


def get(path, timeout=25):
    req = urllib.request.Request(
        BASE + path,
        headers={
            "User-Agent": UA,
            "Accept": "application/json",
            "Accept-Language": "ko-KR,ko;q=0.9",
            "Referer": "https://mabimobi.life/market",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read()
            if r.headers.get("Content-Encoding") == "gzip":
                raw = gzip.decompress(raw)
            return json.loads(raw.decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code == 429:
            raise Throttled(parse_retry_after(e.read().decode("utf-8", "replace")))
        raise


def fetch_prices(on_page=None):
    """시세 전량. 실측 1,226건 / 1.7초, 쿼터 없음.

    on_page(누적건수)를 주면 한 페이지 받을 때마다 부른다 — 화면 진행바용.
    """
    out, offset = [], 0
    while True:
        page = get(f"/market/prices?limit={PRICE_PAGE}&offset={offset}")["items"]
        out += page
        if on_page:
            on_page(len(out))
        if len(page) < PRICE_PAGE:
            return out
        offset += PRICE_PAGE


def fetch_items(keyword):
    q = urllib.parse.quote(keyword)
    return get(f"/items?search={q}&limit=200")["items"]


def fetch_candles(market_kind_id, interval="day"):
    """원본이 주는 일·주·월봉. 쿼터 없음.

    `market_kind_id`는 거래소가 쓰는 진짜 kind_id다 — 재료 매칭에 쓰는
    codex_item_id를 넘기면 404가 난다(실측).

    실측 분량: day 52건(약 2개월) · week 8건 · month 3건.
    """
    return get(f"/market/prices/history?kind_id={market_kind_id}&interval={interval}")[
        "history"
    ]


def fetch_item_detail(item_id):
    """쿼터가 걸린 유일한 엔드포인트. Throttled를 던지면 멈추고 다음 주기에 잇는다."""
    return get(f"/items/{item_id}")
