#!/usr/bin/env python3
"""Fetch current weather + outfit recommendation (Tier 1, 0 tokens).

Uses Open-Meteo API — free, no API key required, WMO standard codes.

Usage:
  python3 fetch_weather.py                        # Seoul, stdout
  python3 fetch_weather.py --location Busan
  python3 fetch_weather.py --output /tmp/weather.json
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from datetime import datetime

# WMO Weather interpretation codes → Korean
WMO_KR = {
    0: "맑음",
    1: "대체로 맑음",
    2: "구름 조금",
    3: "흐림",
    45: "안개",
    48: "결빙 안개",
    51: "가벼운 이슬비",
    53: "이슬비",
    55: "짙은 이슬비",
    56: "결빙 이슬비",
    57: "짙은 결빙 이슬비",
    61: "약한 비",
    63: "비",
    65: "강한 비",
    66: "약한 결빙 비",
    67: "강한 결빙 비",
    71: "약한 눈",
    73: "눈",
    75: "강한 눈",
    77: "싸라기눈",
    80: "약한 소나기",
    81: "소나기",
    82: "강한 소나기",
    85: "약한 눈소나기",
    86: "강한 눈소나기",
    95: "뇌우",
    96: "우박 뇌우",
    99: "강한 우박 뇌우",
}

# WMO codes that indicate rain/snow/ice
WMO_RAIN = {51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82, 95, 96, 99}
WMO_SNOW = {71, 73, 75, 77, 85, 86}
WMO_ICE = {45, 48, 56, 57, 66, 67}

# Locations: name → (lat, lon, korean_name)
LOCATIONS = {
    "Seoul": (37.5665, 126.9780, "서울"),
    "Busan": (35.1796, 129.0756, "부산"),
    "Incheon": (37.4563, 126.7052, "인천"),
    "Daegu": (35.8714, 128.6014, "대구"),
    "Daejeon": (36.3504, 127.3845, "대전"),
    "Gwangju": (35.1595, 126.8526, "광주"),
    "Jeju": (33.4996, 126.5312, "제주"),
    "Suwon": (37.2636, 127.0286, "수원"),
}

# Wind direction: degrees → Korean abbreviation
WIND_DIRS = [
    (22.5, "북"), (67.5, "북동"), (112.5, "동"), (157.5, "남동"),
    (202.5, "남"), (247.5, "남서"), (292.5, "서"), (337.5, "북서"),
    (360.1, "북"),
]


def wind_direction_kr(degrees: float) -> str:
    for threshold, name in WIND_DIRS:
        if degrees < threshold:
            return name
    return "북"


def fetch_open_meteo(lat: float, lon: float) -> dict:
    params = (
        f"latitude={lat}&longitude={lon}"
        "&current=temperature_2m,relative_humidity_2m,apparent_temperature,"
        "weather_code,wind_speed_10m,wind_direction_10m"
        "&daily=temperature_2m_max,temperature_2m_min"
        "&timezone=Asia/Seoul"
    )
    url = f"https://api.open-meteo.com/v1/forecast?{params}"
    req = urllib.request.Request(url, headers={"User-Agent": "mingming-daily/1.0"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode())


def recommend_outfit(
    feels_like: int, wmo_code: int
) -> dict[str, str]:
    """Rule-based outfit recommendation by feels-like temperature."""
    if feels_like <= -10:
        top = "롱패딩 + 히트텍 2장 + 기모 이너"
        bottom = "기모 팬츠"
        extras = "목도리 + 장갑 + 비니 + 귀마개"
    elif feels_like <= -5:
        top = "롱패딩 + 히트텍 + 기모 이너"
        bottom = "기모 팬츠"
        extras = "목도리 + 장갑 + 비니"
    elif feels_like <= 0:
        top = "패딩/두꺼운 코트 + 히트텍 + 니트"
        bottom = "기모 팬츠 or 두꺼운 슬랙스"
        extras = "머플러 + 장갑"
    elif feels_like <= 5:
        top = "패딩/코트 + 니트/맨투맨"
        bottom = "기모 팬츠 or 두꺼운 슬랙스"
        extras = "머플러 + 장갑"
    elif feels_like <= 10:
        top = "코트/자켓 + 니트"
        bottom = "슬랙스 or 청바지"
        extras = "가벼운 머플러"
    elif feels_like <= 15:
        top = "자켓 + 가디건 or 셔츠"
        bottom = "슬랙스 or 청바지"
        extras = ""
    elif feels_like <= 20:
        top = "가벼운 자켓 or 가디건"
        bottom = "면바지 or 청바지"
        extras = ""
    elif feels_like <= 25:
        top = "반팔 or 얇은 긴팔"
        bottom = "반바지 or 면바지"
        extras = ""
    else:
        top = "반팔 + 통풍 좋은 옷"
        bottom = "반바지 or 린넨 팬츠"
        extras = "양산/모자"

    # Weather-specific additions
    if wmo_code in WMO_RAIN:
        extras = (extras + " + 우산").lstrip(" + ")
    if wmo_code in WMO_SNOW:
        extras = (extras + " + 방수 신발").lstrip(" + ")
    if wmo_code in WMO_ICE:
        extras = (extras + " + 도로 결빙 주의").lstrip(" + ")

    summary_parts = [top, bottom]
    if extras:
        summary_parts.append(extras)

    return {
        "top": top,
        "bottom": bottom,
        "extras": extras,
        "summary": ", ".join(summary_parts),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Fetch weather + outfit recommendation")
    ap.add_argument("--location", default="Seoul", help="City name (default: Seoul)")
    ap.add_argument("--output", help="Output JSON file (default: stdout)")
    args = ap.parse_args()

    loc = LOCATIONS.get(args.location)
    if not loc:
        print(f"❌ Unknown location: {args.location}", file=sys.stderr)
        print(f"   Available: {', '.join(LOCATIONS.keys())}", file=sys.stderr)
        sys.exit(1)

    lat, lon, location_kr = loc

    try:
        data = fetch_open_meteo(lat, lon)
    except Exception as e:
        print(f"❌ Weather fetch failed: {e}", file=sys.stderr)
        sys.exit(1)

    cur = data["current"]
    daily = data["daily"]

    temp = round(cur["temperature_2m"])
    feels_like = round(cur["apparent_temperature"])
    humidity = cur["relative_humidity_2m"]
    wmo_code = cur["weather_code"]
    condition_kr = WMO_KR.get(wmo_code, f"코드 {wmo_code}")
    wind_speed = round(cur["wind_speed_10m"])
    wind_dir = wind_direction_kr(cur["wind_direction_10m"])
    high = round(daily["temperature_2m_max"][0])
    low = round(daily["temperature_2m_min"][0])

    outfit = recommend_outfit(feels_like, wmo_code)

    result = {
        "location": location_kr,
        "date": datetime.now().strftime("%Y-%m-%d"),
        "current_temp": temp,
        "feels_like": feels_like,
        "high": high,
        "low": low,
        "humidity": humidity,
        "condition": condition_kr,
        "wmo_code": wmo_code,
        "wind": f"{wind_dir} {wind_speed}km/h",
        "outfit": outfit,
    }

    output = json.dumps(result, ensure_ascii=False, indent=2)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output + "\n")
        print(f"✅ {args.output}", file=sys.stderr)
    else:
        print(output)


if __name__ == "__main__":
    main()
