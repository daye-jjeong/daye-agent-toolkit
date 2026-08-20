"""보유 재료 — 폼 파싱과 쿠키 저장.

재료마다 입력칸을 하나씩 세운다(거래 가능한 18종). 폼 필드 이름은
`qty_<kind_id>`다 — 이름으로 주고받으면 오타·중복 이름에 걸린다.

**재고는 브라우저에 산다.** 서버 DB에 두면 여러 사람이 한 서버를 쓸 때
전원이 한 재고를 공유한다 — A가 저장하면 B 화면의 숫자가 바뀐다.

localStorage가 아니라 쿠키인 이유는 이 페이지가 서버 렌더링이라서다.
실지출 계산도 서버가 한다. 쿠키는 요청에 자동으로 실리므로 정렬 링크·
새로고침·열 토글 어디서든 그 사람의 재고가 따라온다. localStorage였다면
매 요청마다 JS로 재고를 보내고 화면을 다시 그려야 하고, 계산이 Python과
JS로 갈라진다.
"""

from http.cookies import SimpleCookie

COOKIE_NAME = "mabi_inv"
COOKIE_MAX_AGE = 31536000  # 1년. 브라우저를 닫아도 남는다

# 쉼표는 쿠키 구분자라 값에 못 쓴다(RFC 6265 cookie-octet에서 제외).
# `.`과 `:`는 허용되고 따옴표 없이 그대로 실린다.
ITEM_SEP = "."
PAIR_SEP = ":"


def parse_inventory_form(form, valid_ids):
    """폼 딕셔너리 → ({kind_id: 수량}, 못 알아들은 필드).

    빈 칸과 0은 "안 가졌다"이므로 저장하지 않는다. 모르는 id와 음수·비숫자는
    조용히 버리지 않고 돌려준다 — 방금 친 값이라 알려 줄 데가 있다.
    """
    owned, rejected = {}, []
    for field, values in form.items():
        if not field.startswith("qty_"):
            continue
        raw = (values[0] if isinstance(values, list) else values or "").strip()
        if not raw:
            continue
        try:
            kind_id = int(field[4:])
            qty = int(raw.replace(",", ""))
        except ValueError:
            rejected.append(field)
            continue
        if kind_id not in valid_ids or qty < 0:
            rejected.append(field)
            continue
        if qty:
            owned[kind_id] = qty
    return owned, rejected


def encode_inventory(owned):
    """{9283: 80} → "9283:80". id 순으로 세워 같은 재고가 같은 쿠키가 되게 한다."""
    return ITEM_SEP.join(f"{k}{PAIR_SEP}{v}" for k, v in sorted(owned.items()))


def decode_inventory(raw, valid_ids):
    """쿠키 값 → {kind_id: 수량}.

    깨진 항목과 모르는 재료는 그것만 버리고 나머지는 살린다. 폼과 달리
    알릴 데가 없다 — 사용자가 방금 친 값이 아니라 우리가 예전에 쓴 값이다.
    패치로 재료가 바뀌면 여기서 조용히 정리된다.
    """
    out = {}
    for chunk in (raw or "").split(ITEM_SEP):
        key, sep, value = chunk.partition(PAIR_SEP)
        if not sep:
            continue
        try:
            kind_id, qty = int(key), int(value)
        except ValueError:
            continue
        if kind_id in valid_ids and qty > 0:
            out[kind_id] = qty
    return out


def read_inventory_cookie(cookie_header, valid_ids):
    """`Cookie` 헤더 → {kind_id: 수량}. 없거나 깨졌으면 빈 재고."""
    try:
        jar = SimpleCookie(cookie_header or "")
    except Exception:  # 남의 쿠키가 깨져 있어도 우리 페이지는 떠야 한다
        return {}
    morsel = jar.get(COOKIE_NAME)
    return decode_inventory(morsel.value if morsel else "", valid_ids)


def inventory_cookie_header(owned):
    """`Set-Cookie` 헤더 값. 빈 재고면 쿠키를 지운다.

    빈 값을 남기면 그 쿠키가 다음 요청에도 계속 실린다. 비웠다는 건
    "없애 달라"는 뜻이므로 만료시킨다.
    """
    value = encode_inventory(owned)
    max_age = COOKIE_MAX_AGE if value else 0
    return f"{COOKIE_NAME}={value}; Path=/; Max-Age={max_age}; SameSite=Lax; HttpOnly"
