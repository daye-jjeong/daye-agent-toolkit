"""캔들 → 화면에 쓸 추세 요약. 순수 함수.

원본이 일봉을 두 달치 준다. 우리가 3분마다 쌓는 이력과 별개다 —
서버를 처음 띄운 날에도 과거가 있다.

이 파일이 답하는 건 하나다: **지금 사도 되나.**
표에 뜬 단가가 최근 범위의 어디쯤인지가 그 답이다. 실측에서 망령의
영혼석이 하루에 69~108로 움직였다. 그 폭을 모르면 비싼 때 산다.
"""

from datetime import date, datetime, timedelta, timezone

SPARK_DAYS = 14

# 최근 종가 중 몇 %보다 비싼가. 위/아래 30%만 말하고 가운데는 침묵한다.
CHEAP_AT = 0.3
EXPENSIVE_AT = 0.7


def material_trend(candles, now_price):
    """최근 14일 캔들 + 현재가 → 스파크라인과 판정에 필요한 값.

    캔들이 하나도 없으면 None — 아직 안 받았다는 뜻이고, 화면은 단가만 낸다.
    """
    if not candles:
        return None

    recent = candles[-SPARK_DAYS:]
    lows = [c["low"] for c in recent if c.get("low") is not None]
    highs = [c["high"] for c in recent if c.get("high") is not None]
    closes = [c["close"] for c in recent if c.get("close") is not None]
    if not (lows and highs and closes):
        return None

    low, high = min(lows), max(highs)
    today = recent[-1]

    if high == low:
        # 특급 목재가 그렇다 — 14일 내내 146원. 여기서 "비싸다"고 하면 거짓말이다.
        verdict = "flat"
    else:
        # 저가~고가 범위가 아니라 **종가 백분위**로 잰다.
        # 하루 안에 50%씩 움직이는 재료라 low~high는 14일이면 너무 넓어진다 —
        # 실측에서 망령의 영혼석이 종가 60~96인데 범위는 50~139였고, 현재가
        # 111이 "가운데"로 나왔다. 종가로 재면 14일 중 가장 비싼 값이다.
        below = sum(1 for c in closes if c < now_price)
        pos = below / len(closes)
        verdict = (
            "cheap" if pos <= CHEAP_AT else "expensive" if pos >= EXPENSIVE_AT else "middle"
        )

    return {
        "days": len(recent),
        "closes": closes,
        "low": low,
        "high": high,
        "today_low": today.get("low"),
        "today_high": today.get("high"),
        "verdict": verdict,
    }


CHART_DAYS = 30
MIN_POINTS = 3

# 일봉 버킷은 21:00Z에 시작한다 — KST 06:00, 게임의 하루 경계다. 자정이 아니다.
# 실측: 8/19 16:17 KST에 가장 새 캔들이 `2026-08-18T21:00:00Z`였고, 그게
# 그 시각 장중에 계속 움직이던 오늘 캔들이다.
DAY_ROLLS_AT_UTC_HOUR = 21


def _parse(t):
    """`cost._parse`와 같은 계약 — 문자열도 datetime도 받는다.

    `build_report(now=...)`가 둘 다 받아 넘겨서다.
    """
    if isinstance(t, datetime):
        return t if t.tzinfo else t.replace(tzinfo=timezone.utc)
    return datetime.fromisoformat(str(t).replace("Z", "+00:00"))


def _game_day(dt):
    """UTC 시각 → 그 시각이 속한 게임 하루.

    경계를 자정으로 밀어 놓고 날짜만 읽는다. 버킷 시작에도 장중 아무 시각에도
    같은 답을 준다.
    """
    return (dt + timedelta(hours=24 - DAY_ROLLS_AT_UTC_HOUR)).date()


def candle_day(time_str):
    """캔들 하나가 덮는 하루. `2026-08-18T21:00:00Z` → `2026-08-19`."""
    return _game_day(_parse(time_str)).isoformat()


def _usable(candle):
    """그릴 수 있는 하루로 정리한다. 못 그리면 None.

    `close`가 없으면 버린다 — 선을 이을 자리가 없다. `low`·`high`만 없으면
    종가로 대신해 띠가 선 위로 납작해진다. 원본이 필드 이름을 바꿔도
    남은 값으로 그리는 쪽이 빈 화면보다 낫다.
    """
    close = candle.get("close")
    if close is None:
        return None
    low = candle.get("low")
    high = candle.get("high")
    low = close if low is None else min(low, close)
    high = close if high is None else max(high, close)
    return {"date": candle_day(candle["time"]), "low": low, "high": high, "close": close}


def material_chart(candles, now_price, now=None, width=560, height=150):
    """30일 캔들 + 현재가 → 범위 띠 차트에 필요한 값 전부. 좌표까지 여기서 낸다.

    돌려주는 좌표계는 그림판 안쪽이다 — 왼쪽 위가 (0,0), 아래로 갈수록 y가
    크다. 축 여백은 그리는 쪽이 붙인다.

    정통 캔들(몸통+심지)을 쓰지 않는 이유는 우리 값이 "그날 거래소 최저가"의
    OHLC라서다. 몸통 색이 매수·매도 압력을 뜻하지 않는다. 답해야 할 건
    "그때 얼마였고 얼마나 흔들렸나"이고 띠가 그걸 그대로 그린다.

    점이 셋 미만이면 None. 선을 그으려면 둘은 있어야 하고, 둘로는 직선 하나가
    나올 뿐이라 추세라 부를 수 없다. 그때는 빈 차트 대신 "시세 이력 없음"이다.
    """
    pts = [u for u in (_usable(c) for c in candles[-CHART_DAYS:]) if u]
    if len(pts) < MIN_POINTS:
        return None

    lo = min(p["low"] for p in pts)
    hi = max(p["high"] for p in pts)

    # 현재가가 30일 범위를 벗어나면 **범위를 넓힌다.** 삐져나간 것 자체가 지금
    # 가장 중요한 정보다 — 잘라내면 "범위 안에 있다"는 거짓 인상을 준다.
    y_min = min(lo, now_price)
    y_max = max(hi, now_price)
    # 30일 내내 한 값에 붙박인 재료(백금강괴·특급 목재). 0으로 나누지 않고
    # 선을 가운데 둔다. 그리는 쪽은 이 표시를 보고 최고·최저 라벨을 뺀다 —
    # 같은 점에 "최고 132"와 "최저 132"가 겹쳐 봐야 읽을 게 없다.
    flat = y_max == y_min
    if flat:
        y_min, y_max = y_min - 0.5, y_max + 0.5

    span = y_max - y_min
    step = width / (len(pts) - 1)

    def y(v):
        return (y_max - v) / span * height

    for i, p in enumerate(pts):
        p["x"] = i * step
        p["y_low"] = y(p["low"])
        p["y_high"] = y(p["high"])
        p["y_close"] = y(p["close"])

    # 같은 값이 여러 날 나오면 **먼저 온 날**을 짚는다. 언제부터 그 수준이었는지가
    # 알고 싶은 것이다.
    low_at = min(pts, key=lambda p: p["low"])
    high_at = max(pts, key=lambda p: p["high"])

    if flat:
        # 눈금 셋을 그으면 ±1만큼 움직인 것처럼 보인다. 값 하나면 충분하다.
        ticks = [{"value": lo, "y": height / 2}]
    else:
        ticks = []
        for v in (y_max, (y_min + y_max) / 2, y_min):
            label = round(v)
            # 값이 좁게 붙으면 최저·중간·최고가 같은 숫자로 겹친다. 그때는 줄인다.
            if label not in [t["value"] for t in ticks]:
                ticks.append({"value": label, "y": y(v)})

    now_dt = datetime.now(timezone.utc) if now is None else _parse(now)
    as_of = pts[-1]["date"]
    stale_days = (_game_day(now_dt) - date.fromisoformat(as_of)).days

    return {
        "days": len(pts),
        "points": pts,
        "low": {"date": low_at["date"], "value": low_at["low"],
                "x": low_at["x"], "y": low_at["y_low"]},
        "high": {"date": high_at["date"], "value": high_at["high"],
                 "x": high_at["x"], "y": high_at["y_high"]},
        "y_min": y_min,
        "y_max": y_max,
        "flat": flat,
        "now_price": now_price,
        "now_y": y(now_price),
        "ticks": ticks,
        "step": step,
        "width": width,
        "height": height,
        "as_of": as_of,
        "stale_days": max(stale_days, 0),
    }
