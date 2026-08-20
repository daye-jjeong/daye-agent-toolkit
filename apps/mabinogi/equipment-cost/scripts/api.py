"""mabimobi.life 비공식 API 클라이언트.

**원본은 Cloudflare 뒤에 있고, 낡은 TLS 라이브러리로 붙으면 403으로 막는다.**
차단은 요청 횟수와 무관하다 — 손으로 딱 한 번 보내도 막힌다. 403 본문이
Cloudflare 차단 페이지다("Sorry, you have been blocked").

갈리는 건 **파이썬이 어떤 ssl 라이브러리로 빌드됐느냐**다(2026-08-19 실측):

    /usr/bin/python3 3.9.6   LibreSSL 2.8.3   -> 403
    /opt/homebrew/.. 3.14.3  OpenSSL 3.6.3    -> 200
    macOS curl 8.7.1         SecureTransport  -> 403

TLS 버전 문제가 아니다. OpenSSL 쪽을 일부러 TLS 1.2로 낮춰 붙여도 200이다.
HTTP 요청 바이트도 두 인터프리터가 완전히 같다(로컬 소켓으로 받아 비교).
남는 차이는 핸드셰이크 첫 인사(ClientHello)의 생김새뿐이고, Cloudflare가
그걸 지문처럼 써서 구식 클라이언트를 거른다.

그래서 **OpenSSL 3.x로 빌드된 파이썬으로 돌려야 한다**(`deploy/keepalive.sh`가
경로를 박아 둔다). urllib을 쓰는 것 자체는 그대로 두되, 이유는 위와 같다.

**원본 `robots.txt`는 `User-agent: * / Disallow: /`다.** 검색엔진과 광고
크롤러만 허용한다. 이 클라이언트는 그 방침에 어긋난다 — `references/deploy.md`의
"원본 사이트의 방침"을 읽고 쓸지 정할 것.

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
