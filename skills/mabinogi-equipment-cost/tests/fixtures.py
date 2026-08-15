"""2026-08-14T16:17Z 실측 스냅샷.

시세는 계속 움직이므로 테스트는 이 고정 스냅샷만 본다.
단가·매물 수는 /d/api/v1/market/prices 응답에서 그대로 옮겼다.
"""

AS_OF = "2026-08-14T16:17:00Z"

# kind_id -> 시세. 실측값.
PRICES = {
    281479782081111: {"name": "특급 목재", "min_price": 146, "total_count": 162952},
    281479763007481: {"name": "백금강괴", "min_price": 132, "total_count": 223624},
    281481363189525: {"name": "허상의 마력석", "min_price": 55, "total_count": 645},
    281479538461834: {"name": "망령의 영혼석", "min_price": 103, "total_count": 1548},
    281480675678393: {"name": "야생의 영혼석", "min_price": 34, "total_count": 8345},
    281480597107872: {"name": "파동의 영혼석", "min_price": 24, "total_count": 4450},
    281489250918530: {
        "name": "해연의 커브드 하프ZZ",
        "min_price": 23174,
        "total_count": 6,
    },
    281488109695591: {
        "name": "잔영의 커브드 하프ZZ",
        "min_price": 1270,
        "total_count": 6,
    },
    281479000000001: {"name": "운철괴", "min_price": 74, "total_count": 90000},
    281479000000002: {"name": "공명의 영혼석", "min_price": 31, "total_count": 12000},
}

# 일반 제작 재료 6종. 소계 합 15,165 — 망령의 영혼석 8,240이 54.3%를 차지한다.
HAEYEON_HARP_NORMAL = [
    {"kind_id": 281479782081111, "name": "특급 목재", "qty": 5, "can_trade": True},
    {"kind_id": 281479763007481, "name": "백금강괴", "qty": 5, "can_trade": True},
    {"kind_id": 281481363189525, "name": "허상의 마력석", "qty": 15, "can_trade": True},
    {"kind_id": 281479538461834, "name": "망령의 영혼석", "qty": 80, "can_trade": True},
    {"kind_id": 281480675678393, "name": "야생의 영혼석", "qty": 75, "can_trade": True},
    {"kind_id": 281480597107872, "name": "파동의 영혼석", "qty": 90, "can_trade": True},
]

# 레시피 제작. 레시피 1개(거래 불가)가 붙고 나머지 수량이 대략 절반으로 줄어든다.
HAEYEON_HARP_WITH_RECIPE = [
    {
        "kind_id": 10075,
        "name": "레시피: 해연의 커브드 하프ZZ",
        "qty": 1,
        "can_trade": False,
    },
    {"kind_id": 281479782081111, "name": "특급 목재", "qty": 5, "can_trade": True},
    {"kind_id": 281479763007481, "name": "백금강괴", "qty": 5, "can_trade": True},
    {"kind_id": 281481363189525, "name": "허상의 마력석", "qty": 8, "can_trade": True},
    {"kind_id": 281479538461834, "name": "망령의 영혼석", "qty": 40, "can_trade": True},
    {"kind_id": 281480675678393, "name": "야생의 영혼석", "qty": 38, "can_trade": True},
    {"kind_id": 281480597107872, "name": "파동의 영혼석", "qty": 45, "can_trade": True},
]

# 같은 종류 잔영의 일반 제작. 해연보다 재료가 적고 종류도 다르다.
JANYEONG_HARP_NORMAL = [
    {"kind_id": 281479782081111, "name": "특급 목재", "qty": 3, "can_trade": True},
    {"kind_id": 281479000000001, "name": "운철괴", "qty": 3, "can_trade": True},
    {"kind_id": 281479538461834, "name": "망령의 영혼석", "qty": 9, "can_trade": True},
    {"kind_id": 281480675678393, "name": "야생의 영혼석", "qty": 15, "can_trade": True},
    {"kind_id": 281479000000002, "name": "공명의 영혼석", "qty": 16, "can_trade": True},
]

NORMAL_TOTAL = 15165
RECIPE_TOTAL = 8322
MARKET_PRICE = 23174
JANYEONG_MARKET = 1270  # 잔영 1개 시세
JANYEONG_CRAFT_UNIT = 2593  # 잔영 1개 제작비 — 사는 것보다 배 이상 비싸다
JANYEONG_KIND = 281488109695591
