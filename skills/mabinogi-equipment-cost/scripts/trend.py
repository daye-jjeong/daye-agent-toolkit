"""캔들 → 화면에 쓸 추세 요약. 순수 함수.

원본이 일봉을 두 달치 준다. 우리가 3분마다 쌓는 이력과 별개다 —
서버를 처음 띄운 날에도 과거가 있다.

이 파일이 답하는 건 하나다: **지금 사도 되나.**
표에 뜬 단가가 최근 범위의 어디쯤인지가 그 답이다. 실측에서 망령의
영혼석이 하루에 69~108로 움직였다. 그 폭을 모르면 비싼 때 산다.
"""

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
