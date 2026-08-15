"""보유 재료 입력 파싱.

재료마다 입력칸을 하나씩 세운다(거래 가능한 18종). 폼 필드 이름은
`qty_<kind_id>`다 — 이름으로 주고받으면 오타·중복 이름에 걸린다.
"""


def parse_inventory_form(form, valid_ids):
    """폼 딕셔너리 → {kind_id: 수량}.

    빈 칸과 0은 "안 가졌다"이므로 저장하지 않는다. 모르는 id와 음수·비숫자는
    조용히 버리지 않고 돌려준다.
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
