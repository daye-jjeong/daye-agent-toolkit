"""서버 왕복. 재고가 요청마다 그 사람의 쿠키에서 오는지 본다.

렌더링만 테스트하면 "여러 사람이 써도 안 섞인다"는 걸 확인할 수 없다.
그 성질은 핸들러가 저장소 대신 쿠키를 읽느냐에 달려 있어서, 여기서만 보인다.
"""

import http.client
import os
import sys
import threading
from http.server import ThreadingHTTPServer

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import pytest
from inventory import COOKIE_NAME
from refresh import RefreshState
from serve import make_handler
from store import Store

AS_OF = "2026-08-14T16:17:00Z"


@pytest.fixture
def db_path(tmp_path):
    path = str(tmp_path / "s.db")
    s = Store(path)
    s.init()
    s.save_items(
        [
            {
                "id": 1,
                "name": "해연의 커브드 하프ZZ",
                "kind_id": 1,
                "tier": "해연",
                "base_name": "커브드 하프ZZ",
                "category": "Weapon",
                "can_trade": True,
            }
        ]
    )
    s.save_recipe(
        1,
        "normal",
        [{"kind_id": 100, "name": "망령의 영혼석", "qty": 80, "can_trade": True}],
    )
    s.save_prices(
        [
            {
                "kind_id": 1,
                "name": "해연의 커브드 하프ZZ",
                "min_price": 23174,
                "total_count": 6,
            },
            {
                "kind_id": 100,
                "name": "망령의 영혼석",
                "min_price": 103,
                "total_count": 1548,
            },
        ],
        as_of=AS_OF,
    )
    return path


class Client:
    def __init__(self, port):
        self.port = port

    def __call__(self, method, path, body=None, cookie=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        headers = {}
        if body is not None:
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        if cookie:
            headers["Cookie"] = cookie
        conn.request(method, path, body, headers)
        res = conn.getresponse()
        payload = res.read().decode("utf-8")
        out = (res.status, dict(res.getheaders()), payload)
        conn.close()
        return out


def _start(db_path, public=False, collector=None):
    handler = make_handler(
        db_path, 1800, RefreshState(), public=public, collector=collector
    )
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, Client(httpd.server_port)


@pytest.fixture
def local(db_path):
    httpd, client = _start(db_path)
    yield client
    httpd.shutdown()


@pytest.fixture
def public(db_path):
    httpd, client = _start(db_path, public=True)
    yield client
    httpd.shutdown()


# --- 재고는 그 사람의 쿠키에서 온다 -------------------------------------------


def test_saving_inventory_sets_a_cookie(local):
    status, headers, _ = local("POST", "/inventory", "qty_100=30")
    assert status == 303
    assert f"{COOKIE_NAME}=100:30" in headers["Set-Cookie"]


def test_the_server_forgets_the_inventory_between_visitors(local):
    """저장한 다음 쿠키 없이 오면 재고가 없어야 한다 — 남으면 전원 공유다."""
    local("POST", "/inventory", "qty_100=30")
    _, _, page = local("GET", "/")
    assert "실 제작" not in page


def test_the_cookie_brings_the_inventory_back(local):
    _, headers, _ = local("POST", "/inventory", "qty_100=30")
    cookie = headers["Set-Cookie"].split(";")[0]
    _, _, page = local("GET", "/", cookie=cookie)
    assert "실 제작" in page
    assert "5,150" in page  # 103 × (80 − 30)


def test_two_cookies_do_not_see_each_other(local):
    _, _, mine = local("GET", "/", cookie=f"{COOKIE_NAME}=100:80")
    _, _, yours = local("GET", "/", cookie=f"{COOKIE_NAME}=100:10")
    assert "실 제작" in mine and "실 제작" in yours
    assert "7,210" in yours  # 103 × 70
    assert "7,210" not in mine


def test_clearing_the_inventory_expires_the_cookie(local):
    _, headers, _ = local("POST", "/inventory", "qty_100=0")
    assert "Max-Age=0" in headers["Set-Cookie"]


# --- 예전 재고 넘겨받기 ---------------------------------------------------------


@pytest.fixture
def legacy_db(db_path):
    """재고를 서버 DB에 두던 시절의 DB."""
    import sqlite3

    with sqlite3.connect(db_path) as c:
        c.execute("CREATE TABLE inventory (kind_id INTEGER PRIMARY KEY, qty INTEGER)")
        c.execute("INSERT INTO inventory VALUES (100, 30)")
    return db_path


def test_old_server_side_inventory_hands_off_to_the_browser(legacy_db):
    httpd, client = _start(legacy_db)
    try:
        _, headers, page = client("GET", "/")
        assert f"{COOKIE_NAME}=100:30" in headers["Set-Cookie"]
        assert "실 제작" in page  # 넘겨받은 재고가 그 화면에 이미 반영돼 있다

        # 두 번째 방문자는 남의 재고를 물려받지 않는다
        _, headers2, page2 = client("GET", "/")
        assert "Set-Cookie" not in headers2
        assert "실 제작" not in page2
    finally:
        httpd.shutdown()


# --- 공개 배포 모드 -------------------------------------------------------------


def test_refresh_button_is_gone_in_public_mode(public):
    _, _, page = public("GET", "/")
    assert 'id="reload"' not in page


def test_refresh_endpoint_is_closed_in_public_mode(public):
    status, _, _ = public("POST", "/refresh", "")
    assert status == 404


def test_refresh_still_works_locally(local):
    _, _, page = local("GET", "/")
    assert 'id="reload"' in page


def test_a_failed_collection_reaches_the_visitors_page(db_path, monkeypatch):
    """방문자는 서버 콘솔을 못 본다. 실패는 화면에 있어야 한다."""
    import serve
    from refresh import CollectorStatus

    def boom(store, on_page=None):
        raise OSError("네트워크 끊김")

    monkeypatch.setattr(serve, "collect_prices", boom)

    status = CollectorStatus()
    assert serve.collect_once(Store(db_path), status) is False

    httpd, client = _start(db_path, public=True, collector=status)
    try:
        _, _, page = client("GET", "/")
        assert "시세 수집 실패" in page
        assert "네트워크 끊김" in page
    finally:
        httpd.shutdown()


def test_a_recovered_collector_stops_warning(db_path):
    from refresh import CollectorStatus

    status = CollectorStatus()
    status.failed("OSError: 네트워크 끊김")
    status.ok()

    httpd, client = _start(db_path, public=True, collector=status)
    try:
        _, _, page = client("GET", "/")
        assert "시세 수집 실패" not in page
    finally:
        httpd.shutdown()
