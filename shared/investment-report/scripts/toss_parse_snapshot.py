#!/usr/bin/env python3
"""Parse Toss US portfolio table from openclaw browser aria snapshot JSON.

Expected input: JSON from Clawdbot browser snapshot (aria).
Output: list of {name, avg_price, qty, currency}.

Heuristic:
- Find rows (role=row) under the table for 해외주식.
- For each row, take the first cell's StaticText as name.
- Then within the same row, collect StaticText values that match:
  - avg price: $<number> (column '1주 평균금액')
  - qty: <number> 주
We assume currency USD.

This is brittle but good enough to seed Positions.
"""

import json
import re
import sys

USD = re.compile(r'^\$([0-9][0-9,]*\.?[0-9]*)$')
QTY = re.compile(r'^([0-9]+\.?[0-9]*)\s*주$')


def main():
    data = json.load(sys.stdin)
    nodes = data.get('nodes', [])
    # Build map ref -> node
    by_ref = {n['ref']: n for n in nodes if 'ref' in n}

    # In compact aria snapshot, children aren't explicit. We'll just scan nodes list for rows.
    rows = [n for n in nodes if n.get('role') == 'row' and '종목 상세 페이지로 이동' in (n.get('name') or '')]

    results = []
    for r in rows:
        # Gather subsequent nodes until next row at same depth appears (heuristic)
        start_idx = nodes.index(r)
        # scan forward
        name = None
        avg = None
        qty = None
        for n in nodes[start_idx+1:]:
            if n.get('role') == 'row' and '종목 상세 페이지로 이동' in (n.get('name') or ''):
                break
            if n.get('role') == 'StaticText':
                t = (n.get('name') or '').strip()
                if not t:
                    continue
                if name is None and not t.startswith('$') and not t.endswith('%') and '주' not in t and ',' not in t and t not in ('-', '(', ')'):
                    # too strict; ignore
                    pass
                # Better: the first meaningful Korean name is usually present
                if name is None and any(ch.isalpha() for ch in t) and not USD.match(t) and not QTY.match(t) and not t.endswith('%') and not t.startswith('logo'):
                    name = t
                m = USD.match(t)
                if m and avg is None:
                    # first $ value after return% and return$ might not be avg; we can't disambiguate well.
                    # We'll collect all $ values then pick the 3rd one as avg in practice.
                    pass
        # second pass: collect all $ values and qty values
        dollars=[]
        for n in nodes[start_idx+1:]:
            if n.get('role') == 'row' and '종목 상세 페이지로 이동' in (n.get('name') or ''):
                break
            if n.get('role') == 'StaticText':
                t=(n.get('name') or '').strip()
                m=USD.match(t)
                if m:
                    dollars.append(float(m.group(1).replace(',','')))
                mq=QTY.match(t)
                if mq and qty is None:
                    qty=float(mq.group(1))
        # Heuristic: dollars appear in order: profit$, avg$, price$, valuation$, principal$, daily%, daily$, fee$, tax$ ...
        # On our page we saw for first row: -$1,090.49, $99.46, $59.57, $1,620.40, $2,710.89, ...
        if dollars:
            avg = dollars[1] if len(dollars) > 1 else dollars[0]
        if name and avg is not None and qty is not None:
            results.append({'name': name, 'avg_price': avg, 'qty': qty, 'currency': 'USD'})

    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
