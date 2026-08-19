#!/usr/bin/env python3
"""비교 페이지 서버.

    python3 serve.py [포트] [DB경로] [신선도임계초] [--public]

`--public`은 여러 사람이 쓰는 배포판이다 — `0.0.0.0`에 바인딩하고,
새로고침 버튼을 끄고, 서버가 직접 주기 수집을 돈다. 버튼을 남겨 두면
방문자마다 원본 API를 때려 서버 IP 하나로 요청이 몰린다.

원가는 전부 `최저가 × 수량`이라 하한선이다. 페이지가 그 사실을 숨기지 않는다.
"""

import html
import json
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from collect import DEFAULT_INTERVAL, collect_candles, collect_prices
from classify import group_materials
from cost import DEFAULT_ECHO_MULTIPLIER, DEFAULT_STALE_SEC
from inventory import (
    inventory_cookie_header,
    parse_inventory_form,
    read_inventory_cookie,
)
from refresh import CollectorStatus, RefreshState
from report import build_report
from store import DEFAULT_DB, Store

CSS = """
:root { --bg:#fff; --fg:#1a1a1a; --dim:#6b7280; --line:#e5e7eb; --head:#f9fafb;
        --good:#047857; --bad:#b91c1c; --warn:#b45309; --warnbg:#fef3c7; }
@media (prefers-color-scheme: dark) {
  :root { --bg:#111827; --fg:#f3f4f6; --dim:#9ca3af; --line:#374151; --head:#1f2937;
          --good:#34d399; --bad:#f87171; --warn:#fbbf24; --warnbg:#422006; } }
* { box-sizing:border-box; }
body { margin:0; padding:24px; background:var(--bg); color:var(--fg);
       font:14px/1.5 -apple-system,BlinkMacSystemFont,"Apple SD Gothic Neo",sans-serif; }
h1 { font-size:20px; margin:0 0 4px; }
.sub { color:var(--dim); font-size:13px; margin-bottom:16px; }
.bar { display:flex; gap:16px; align-items:center; flex-wrap:wrap;
       padding:10px 14px; border:1px solid var(--line); border-radius:8px;
       margin-bottom:16px; }
.stale { background:var(--warnbg); border-color:var(--warn); color:var(--warn);
         font-weight:600; }
.wrap { overflow-x:auto; }
table { border-collapse:collapse; width:100%; min-width:880px; }
th,td { padding:7px 10px; border-bottom:1px solid var(--line); text-align:right;
        white-space:nowrap; }
th { background:var(--head); position:sticky; top:0; text-align:right;
     font-weight:600; font-size:12px; color:var(--dim); white-space:nowrap; }
th a { color:inherit; text-decoration:none; }
th a:hover { text-decoration:underline; }
th.sorted { color:var(--fg); }
th:first-child, td:first-child { text-align:left; }
tbody tr:hover { background:var(--head); }
.tier { font-size:11px; padding:1px 6px; border-radius:4px; border:1px solid var(--line);
        color:var(--dim); margin-right:6px; }
.craft { color:var(--good); font-weight:600; }
.buy { color:var(--bad); font-weight:600; }
.na { color:var(--dim); }
.note { color:var(--dim); font-size:12px; margin-top:10px; }
.note a { color:var(--dim); }
.intro { margin:0 0 16px; padding:0 0 0 18px; color:var(--dim); font-size:13px; }
.intro li { margin:2px 0; }
.intro b { color:var(--fg); font-weight:600; }
.grp td { background:var(--head); font-weight:700; font-size:12px;
          border-top:2px solid var(--line); letter-spacing:.02em; }
.toggles { display:flex; gap:16px; margin:0 0 10px; }
.toggle a { display:inline-flex; align-items:center; gap:6px; font-size:13px;
  color:var(--dim); text-decoration:none; }
.toggle a:hover { color:var(--fg); }
.toggle input { pointer-events:none; margin:0; }
td.win { font-weight:700;
  background:color-mix(in srgb, var(--good) 12%, transparent); }
tr.row[data-detail] { cursor:pointer; }
tr.row .caret { display:inline-block; color:var(--dim); font-size:11px;
  transition:transform .15s ease; }
tr.row.open .caret { transform:rotate(90deg); }
tr.detail > td { background:var(--head); padding:12px 14px 16px 26px; }
.paths { display:grid; gap:12px; align-items:start;
  grid-template-columns:repeat(auto-fit,minmax(320px,1fr)); }
.path { background:var(--bg); border:1px solid var(--line); border-radius:8px;
  overflow:hidden; }
.path h5 { margin:0; padding:7px 12px; font-size:12px; font-weight:600;
  color:var(--dim); background:var(--head); border-bottom:1px solid var(--line);
  letter-spacing:.02em; }
details { margin:0; }
summary { cursor:pointer; list-style:none; }
summary::-webkit-details-marker { display:none; }
summary::before { content:"▸ "; color:var(--dim); }
details[open] summary::before { content:"▾ "; }
.mat { margin:0; min-width:0; width:100%; font-size:13px; }
.mat th { position:static; background:transparent; padding:6px 10px 4px;
  border-bottom:1px solid var(--line); font-size:11px; }
.mat td { padding:4px 10px; border-bottom:none; }
.mat tbody tr:nth-child(odd) td { background:color-mix(in srgb,var(--head) 55%,transparent); }
.mat tbody tr:hover td { background:var(--head); }
.mat tr.sum td { border-top:1px solid var(--line); font-weight:700;
  background:transparent !important; }
.flag { color:var(--warn); font-size:12px; }
.oop { color:var(--good); font-size:12px; }
textarea { width:100%; max-width:520px; min-height:110px; padding:8px;
  background:var(--bg); color:var(--fg); border:1px solid var(--line);
  border-radius:6px; font:13px/1.5 ui-monospace,SFMono-Regular,monospace; }
details.inv { margin:16px 0; border:1px solid var(--line); border-radius:8px;
  padding:10px 14px; }
details.inv summary { font-weight:600; }
.matgroup { margin:12px 0; }
.matgroup h4 { margin:0 0 6px; font-size:12px; color:var(--dim);
  font-weight:600; letter-spacing:.02em; }
.matgrid { display:grid; gap:10px 16px;
  grid-template-columns:repeat(auto-fill,minmax(232px,1fr)); }
.matinput { display:grid; grid-template-columns:1fr 76px; align-items:center;
  gap:4px 8px; font-size:13px; }
.mtrend { grid-column:1 / -1; display:flex; align-items:center; gap:6px;
  font-size:11px; color:var(--dim); white-space:nowrap; }
.mtrend b { color:var(--fg); font-weight:600; font-size:12px; }
.mtrend svg { display:block; flex:none; }
.spark { color:var(--dim); }
.spark.up { color:var(--bad); }
.spark.down { color:var(--good); }
.invval { margin:12px 0 0; padding-top:10px; border-top:1px solid var(--line);
  font-size:12px; color:var(--dim); }
.invval b { color:var(--fg); }
.matinput input { width:82px; padding:3px 6px; background:var(--bg);
  color:var(--fg); border:1px solid var(--line); border-radius:4px;
  text-align:right; }
#reload { padding:4px 12px; cursor:pointer; }
#reload[disabled] { opacity:.55; cursor:progress; }
#prog { display:none; flex:1 1 220px; min-width:180px; align-items:center; gap:10px; }
#prog.on { display:flex; }
#track { flex:1; height:6px; border-radius:3px; background:var(--line);
  overflow:hidden; }
#fill { height:100%; width:0; background:var(--good); border-radius:3px;
  transition:width .25s ease; }
#fill.spin { width:35%; animation:slide 1.1s ease-in-out infinite; }
@keyframes slide { 0% { margin-left:-35%; } 100% { margin-left:100%; } }
#ptext { font-size:12px; color:var(--dim); white-space:nowrap; }
#ptext.bad { color:var(--warn); }
input[type=number] { width:64px; padding:3px 6px; background:var(--bg);
                     color:var(--fg); border:1px solid var(--line); border-radius:4px; }
"""


# 새로고침 버튼. 서버가 알려주는 실제 수집 건수로 진행바를 그린다 —
# 총량은 받아 보기 전엔 모르므로 직전 건수를 추정치로 쓰고, 없으면 흐르는 막대만 둔다.
RELOAD_JS = """
(function () {
  var btn = document.getElementById('reload');
  if (!btn) return;
  var box = document.getElementById('prog'),
      fill = document.getElementById('fill'),
      text = document.getElementById('ptext');

  function show(msg, percent, bad) {
    box.classList.add('on');
    text.textContent = msg;
    text.classList.toggle('bad', !!bad);
    if (percent === null || percent === undefined) {
      fill.classList.add('spin');
      fill.style.width = '';
    } else {
      fill.classList.remove('spin');
      fill.style.width = percent + '%';
    }
  }

  function poll() {
    fetch('/refresh/status').then(function (r) { return r.json(); }).then(function (s) {
      if (s.state === 'running') {
        show(s.fetched.toLocaleString() + '건 받는 중', s.percent);
        return setTimeout(poll, 300);
      }
      if (s.state === 'error') {
        show('실패: ' + s.error, 0, true);
        btn.disabled = false;
        return;
      }
      show(s.fetched.toLocaleString() + '건 받음', 100);
      location.reload();
    }).catch(function (e) {
      show('상태를 못 받았다: ' + e, 0, true);
      btn.disabled = false;
    });
  }

  btn.addEventListener('click', function () {
    btn.disabled = true;
    show('시작하는 중', null);
    fetch('/refresh', { method: 'POST' })
      .then(function () { poll(); })
      .catch(function (e) {
        show('시작하지 못했다: ' + e, 0, true);
        btn.disabled = false;
      });
  });
})();

// 시각은 UTC로 내려온다. 보는 사람의 시간대로 바꾼다.
(function () {
  document.querySelectorAll('time[datetime]').forEach(function (t) {
    var d = new Date(t.dateTime);
    if (isNaN(d)) return;
    var hm = d.toLocaleTimeString([], {
      hour: '2-digit', minute: '2-digit', hour12: false
    });
    t.textContent = t.hasAttribute('data-day')
      ? d.toLocaleDateString([], { month: '2-digit', day: '2-digit' }) + ' ' + hm
      : hm;
  });
})();

// 행을 누르면 바로 아래 상세 행이 열린다.
(function () {
  document.querySelectorAll('tr.row[data-detail]').forEach(function (tr) {
    tr.addEventListener('click', function (e) {
      if (e.target.closest('a, input, button, label')) return;
      var d = document.getElementById(tr.dataset.detail);
      if (!d) return;
      d.hidden = !d.hidden;
      tr.classList.toggle('open', !d.hidden);
    });
  });
})();

// 저장을 누르기 전에 페이지가 바뀌어도 입력이 날아가지 않게 붙든다.
// 저장된 값(서버가 채워 준 값)과 다를 때만 되살리고, 그 사실을 알린다.
(function () {
  var KEY = 'mabi-inventory-draft';
  var form = document.querySelector('form[action="/inventory"]');
  if (!form || !window.localStorage) return;
  var inputs = form.querySelectorAll('input[type=number]');

  function current() {
    var o = {};
    inputs.forEach(function (i) { o[i.name] = i.value; });
    return o;
  }

  var saved = current();          // 서버가 채워 준 값 = 저장된 상태
  var draft = null;
  try { draft = JSON.parse(localStorage.getItem(KEY) || 'null'); } catch (e) { draft = null; }

  if (draft) {
    var changed = 0;
    inputs.forEach(function (i) {
      if (draft[i.name] !== undefined && draft[i.name] !== saved[i.name]) {
        i.value = draft[i.name];
        changed++;
      }
    });
    if (changed) {
      var note = document.createElement('p');
      note.className = 'note flag';
      note.textContent = '저장하지 않은 입력 ' + changed + '칸을 되살렸다. 저장을 눌러야 표에 반영된다.';
      form.insertBefore(note, form.firstChild);
      form.closest('details').open = true;
    }
  }

  var clear = document.getElementById('clear-inv');
  if (clear) {
    clear.addEventListener('click', function () {
      inputs.forEach(function (i) { i.value = 0; });
      form.dispatchEvent(new Event('input'));   // 초안에도 반영
    });
  }

  form.addEventListener('input', function () {
    try { localStorage.setItem(KEY, JSON.stringify(current())); } catch (e) {}
  });
  form.addEventListener('submit', function () {
    try { localStorage.removeItem(KEY); } catch (e) {}
  });
})();
"""


def _n(v):
    return f"{v:,}" if isinstance(v, int) else "—"


def excluded_label(names):
    """합계에서 뺀 재료를 이름으로 말한다.

    거래 불가는 레시피 아이템만이 아니다 — `세공된 페리도트ZZ`가 그렇다.
    무조건 "레시피 제외"라고 쓰면 페리도트 계열에서 거짓말이 된다.
    """
    if not names:
        return ""
    if all(n.startswith("레시피: ") for n in names):
        return "레시피 제외"
    if len(names) == 1:
        return f"{names[0]} 제외"
    return f"거래 불가 {len(names)}종 제외"


def _oop_cell(path):
    """실지출 칸. 전체 시세와 열을 나눠야 각각 정렬할 수 있다."""
    if path is None or path["status"] != "ok":
        return '<span class="na">—</span>'
    return f'<span class="oop">{_n(path.get("out_of_pocket"))}</span>'


def _path_cell(path, show_oop=False):
    """제작 경로 한 칸. 왜 못 세는지가 값보다 중요하다."""
    if path is None:
        return '<span class="na">—</span>'
    s = path["status"]
    if s == "not_collected":
        return '<span class="na">수집 중</span>'
    if s == "uncomputable":
        return '<span class="na" title="%s">계산 불가</span>' % html.escape(
            ", ".join(path["missing_price"]) + " 시세 없음"
        )
    out = _n(path["total"])
    if path["shortage_warnings"]:
        out += ' <span class="flag" title="%s">매물 부족</span>' % html.escape(
            ", ".join(path["shortage_warnings"])
        )
    return out


def _materials_table(path, label, show_owned=False):
    """경로 하나의 재료 내역.

    소계가 큰 순으로 세운다 — 원가를 무엇이 지배하는지가 이 표를 여는 이유다.
    가진 재료가 있으면 필요·보유·살 것을 나눠 보이고, 합계에 실지출을 함께 낸다.
    """
    if not path or not path["materials"]:
        return ""

    mats = sorted(path["materials"], key=lambda m: -(m["subtotal"] or 0))
    rows = []
    for m in mats:
        flag = ""
        if m.get("untradable"):
            flag = '<span class="na">거래소에 없음</span>'
        elif m["unit_price"] is None:
            flag = '<span class="flag">시세 없음</span>'
        elif m["shortage"]:
            flag = '<span class="flag">매물 %s개 &lt; 살 것 %s개</span>' % (
                _n(m["listing_count"]),
                _n(m.get("need", m["qty"])),
            )
        owned_cells = real_cell = ""
        if show_owned:
            have = m.get("owned", 0)
            need = m.get("need", m["qty"])
            owned_cells = (
                f'<td class="{"oop" if have else "na"}">{_n(have)}</td>'
                f"<td>{_n(need)}</td>"
            )
            real_cell = f'<td class="oop">{_n((m["unit_price"] or 0) * need)}</td>'
        rows.append(
            f"<tr><td>{html.escape(m['name'])}</td><td>{_n(m['qty'])}</td>"
            f"{owned_cells}"
            f'<td class="na">{_n(m["unit_price"])}</td><td>{_n(m["subtotal"])}</td>'
            f"{real_cell}"
            f'<td class="na">{_n(m["listing_count"])}</td><td>{flag}</td></tr>'
        )

    span = 4 if show_owned else 2
    real_total = (
        f'<td class="oop">{_n(path.get("out_of_pocket"))}</td>' if show_owned else ""
    )
    rows.append(
        f'<tr class="sum"><td colspan="{span}">합계</td><td></td>'
        f'<td>{_n(path["total"])}</td>{real_total}<td colspan="2"></td></tr>'
    )

    owned_head = "<th>보유</th><th>살 것</th>" if show_owned else ""
    real_head = "<th>실 소계</th>" if show_owned else ""
    return (
        f'<section class="path"><h5>{label}</h5>'
        f'<table class="mat"><thead><tr><th>재료</th><th>필요</th>'
        f"{owned_head}<th>단가</th><th>소계</th>{real_head}<th>매물</th><th></th>"
        "</tr></thead><tbody>" + "".join(rows) + "</tbody></table></section>"
    )


def _echo_cell(echo):
    """같은 종류 잔영 N개 값. 한 개 단가를 함께 보여 배수 감각을 잃지 않게 한다."""
    if echo["status"] != "ok":
        return '<span class="na">—</span>'
    return f'{_n(echo["total"])} <span class="na">@{_n(echo["unit"])}</span>'


def _verdict_cell(row, multiplier):
    """가장 싼 길 하나. 해연을 그냥 살 때보다 얼마나 아끼는지 함께 보인다."""
    best = row["cheapest"]
    if best is None:
        return '<span class="na">—</span>'

    label = best["label"].replace("잔영", f"잔영×{multiplier}")
    if best["option"] == "buy":
        return f'<span class="na">{label}</span>'
    if row["market"]["status"] != "ok":
        return f'<span class="craft">{label}</span> <span class="na">매물 없음</span>'
    gap = row["market"]["price"] - best["price"]
    return f'<span class="craft">{label} −{_n(gap)}</span>'


VERDICT_LABELS = {
    "cheap": ("싼 편", "oop"),
    "expensive": ("비싼 편", "flag"),
    "flat": ("고정", "na"),
    "middle": ("", ""),
}


def _sparkline(closes, width=72, height=18):
    """종가 몇 개를 선 하나로. 라이브러리 없이 polyline 하나면 된다.

    눈금도 축도 없다 — 여기서 답할 건 "오르는 중인가"뿐이고, 정확한 값은
    옆에 숫자로 있다.
    """
    if len(closes) < 2:
        return ""
    low, high = min(closes), max(closes)
    span = (high - low) or 1
    step = width / (len(closes) - 1)
    pts = " ".join(
        f"{i * step:.1f},{height - 1 - (v - low) / span * (height - 2):.1f}"
        for i, v in enumerate(closes)
    )
    # 오르는 중이면 붉게 — 사는 쪽에서는 오르는 게 나쁜 소식이다.
    way = "up" if closes[-1] > closes[0] else "down" if closes[-1] < closes[0] else ""
    return (
        f'<svg class="spark {way}" width="{width}" height="{height}"'
        f' viewBox="0 0 {width} {height}" aria-hidden="true">'
        f'<polyline points="{pts}" fill="none" stroke="currentColor"'
        ' stroke-width="1.5" stroke-linejoin="round" stroke-linecap="round"/></svg>'
    )


def _material_trend_row(detail):
    """입력칸 아래 한 줄 — 현재 단가, 14일 선, 오늘 범위, 지금 사도 되는지."""
    if not detail or detail.get("price") is None:
        return ""
    bits = [f"<b>{_n(detail['price'])}</b>"]
    t = detail.get("trend")
    if t:
        bits.append(_sparkline(t["closes"]))
        if t["today_low"] is not None and t["today_high"] is not None:
            bits.append(f"오늘 {_n(t['today_low'])}~{_n(t['today_high'])}")
        label, cls = VERDICT_LABELS.get(t["verdict"], ("", ""))
        if label:
            bits.append(f'<span class="{cls}">{label}</span>')
    return '<span class="mtrend">' + " ".join(bits) + "</span>"


def _inventory_form(materials, owned, rejected=0, details=None, inventory_value=0):
    """가진 재료를 재료별 칸으로 받는다.

    거래 가능한 재료만 세운다(실측 18종). 적어 두면 제작 칸에 실지출이 함께
    나온다. 판정은 전체 시세로 한다 — 가진 재료도 팔 수 있어서다.
    """
    warn = (
        f'<p class="note flag">{rejected}칸을 알아듣지 못해 넘어갔다 —'
        " 숫자만 넣을 것</p>"
        if rejected
        else ""
    )
    cells = "".join(
        f'<div class="matgroup"><h4>{html.escape(g["label"])}</h4>'
        '<div class="matgrid">'
        + "".join(
            f'<label class="matinput"><span>{html.escape(name)}</span>'
            f'<input type="number" name="qty_{kind_id}" min="0" step="1"'
            f' value="{owned.get(kind_id, 0)}">'
            f"{_material_trend_row((details or {}).get(kind_id))}</label>"
            for name, kind_id in g["items"]
        )
        + "</div></div>"
        for g in group_materials(materials)
    )
    held = sum(1 for _, k in materials if owned.get(k))
    summary = f"가진 재료 ({held}종 입력됨)" if held else "가진 재료"
    value_line = (
        f'<p class="invval">내 재고 가치 <b>{_n(inventory_value)}</b>'
        " · 최저가 기준 · 재료를 그냥 팔 때 받는 하한선</p>"
        if inventory_value
        else ""
    )
    return (
        # 늘 접힌 채로 연다. 열 체크박스를 눌러 페이지가 갱신될 때마다 펼쳐지면
        # 표가 아래로 밀려 눌린 곳을 다시 찾아야 한다.
        '<details class="inv">'
        f"<summary>{summary}</summary>"
        f'{warn}<form method="post" action="/inventory">'
        f"{cells}"
        f"{value_line}"
        '<p><button type="submit">저장</button> '
        '<button id="clear-inv" type="button">모두 비우기</button>'
        ' <span class="na">비우기는 칸만 0으로 채운다 — 저장을 눌러야 반영된다</span></p>'
        "</form></details>"
    )


# 공개판은 서버가 주기로 받으므로 임계도 그 주기를 따라간다.
PUBLIC_STALE_SEC = DEFAULT_INTERVAL * 5

RELOAD_UI = (
    '<button id="reload" type="button">새로고침</button>'
    '<span id="prog"><span id="track"><span id="fill"></span></span>'
    '<span id="ptext"></span></span>'
)


def _collector_bar(collector):
    """주기 수집이 실패하고 있으면 그 사실과 이유를 띄운다.

    방문자는 서버 콘솔을 못 본다. 아무 말 없이 낡은 값을 보여 주면 그게
    최신인 줄 안다.
    """
    if not collector or not collector.get("error"):
        return ""
    streak = collector.get("failures", 1)
    return (
        '<div class="bar stale">시세 수집 실패'
        f"{f' ({streak}번 연속)' if streak > 1 else ''} —"
        f" {html.escape(str(collector['error']))}."
        f" {DEFAULT_INTERVAL // 60}분 뒤 다시 시도한다</div>"
    )


def _clock(ts, age_sec=None):
    """시각 한 칸. UTC로 적고 브라우저가 로컬 시각으로 바꾼다.

    원본이 주는 값은 UTC다. `07:36`이라고만 쓰면 한국에서 보는 사람은 9시간
    어긋난 걸 모른다. JS가 안 돌면 `07:36 UTC`가 그대로 남는다.
    하루가 넘었으면 날짜를 붙인다.
    """
    text = str(ts)
    parts = text.replace("Z", "").split("T")
    if len(parts) != 2 or len(parts[1]) < 5:
        return html.escape(text)  # 모양이 다르면 원문 그대로 — 지어내지 않는다
    day, hhmm = parts[0], parts[1][:5]
    over_a_day = age_sec is not None and age_sec >= 86400
    label = f"{day[5:]} {hhmm}" if over_a_day else hhmm
    return (
        f'<time datetime="{html.escape(text)}"{" data-day" if over_a_day else ""}>'
        f"{html.escape(label)} UTC</time>"
    )


LOG_FIELD_LIMIT = 200


def log_safe(text, limit=LOG_FIELD_LIMIT):
    """방문자가 보낸 값을 로그 한 줄에 넣을 수 있게 다듬는다.

    셋을 처리한다.

    - HTTP 헤더는 latin-1로 디코딩돼 들어온다. UTF-8을 보낸 클라이언트의 값은
      되돌려 읽어야 글자가 안 깨진다
    - 제어문자를 지운다. 안 그러면 방문자가 User-Agent로 가짜 로그 줄을 만든다
    - 길이를 자른다. 5,000자짜리 User-Agent로 로그를 부풀리는 걸 막는다
    """
    try:
        text = text.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        pass  # 원래 UTF-8이 아니었다 — 있는 그대로 쓴다
    return "".join(c for c in text if c.isprintable())[:limit] or "-"


def _ago(sec):
    """ "3분 전". 큰 값은 시간·일로 접는다 — "1500분 전"은 눈으로 못 읽는다."""
    minutes = sec // 60
    if minutes < 120:
        return f"{minutes}분 전"
    if minutes < 2880:
        return f"{minutes // 60}시간 전"
    return f"{minutes // 1440}일 전"


def _freshness_message(f, public):
    """띠에 쓸 문장. 두 시계 중 무엇을 말할지가 여기서 갈린다.

    경고는 "우리가 마지막으로 받은 게 언제인가"로 낸다. 원본 스냅샷 시각은
    여기서 답이 아니다 — 원본이 늦는 건 우리가 못 고치고 방문자도 할 게 없다.
    """
    if f["stale"]:
        # 공개판에서는 방문자가 수집기를 손댈 수 없다. 할 수 없는 일을 시키지 않는다.
        why = "자동 갱신이 멈춘 것 같다" if public else "수집기가 멈췄는지 확인할 것"
        limit = f"임계 {f['threshold_sec'] // 60}분을 넘었다"
        if f.get("fetch_age_sec") is None:  # 수집 시각을 기록하기 전에 쌓인 DB
            return (
                f"시세 기준 {_clock(f['as_of'], f['age_sec'])}"
                f" · {_ago(f['age_sec'])} — {limit}. {why}"
            )
        return (
            f"마지막 수집 {_clock(f['fetched_at'], f['fetch_age_sec'])}"
            f" · {_ago(f['fetch_age_sec'])} — {limit}. {why}"
        )

    out = f"시세 기준 {_clock(f['as_of'], f['age_sec'])} · {_ago(f['age_sec'])}"
    if f.get("source_lagging"):
        out += " · 원본이 그 뒤로 새 값을 안 준다"
    if f.get("fetch_age_sec") is not None:
        out += f" · {_clock(f['fetched_at'], f['fetch_age_sec'])}에 받음"
    return out


def render_html(
    rep,
    show_recipe=False,
    show_echo_craft=False,
    materials=(),
    owned=None,
    rejected=0,
    public=False,
    collector=None,
):
    inv_form = _inventory_form(
        materials,
        owned or {},
        rejected,
        details={m["kind_id"]: m for m in rep.get("materials", [])},
        inventory_value=rep.get("inventory_value", 0),
    )
    f = rep["freshness"]
    if f is None:
        bar = '<div class="bar stale">시세를 아직 한 번도 받지 못했다</div>'
    else:
        cls = "bar stale" if f["stale"] else "bar"
        msg = _freshness_message(f, public)
        bar = (
            f'<div class="{cls}"><span>{msg}</span>'
            f"{'' if public else RELOAD_UI}"
            '<form method="get" style="margin-left:auto">'
            f'<input type="hidden" name="recipe" value="{1 if show_recipe else 0}">'
            f'<label>잔영 배수 <input type="number" name="echo" min="1" max="99"'
            f' value="{rep["echo_multiplier"]}"></label> '
            "<button>적용</button></form></div>"
        )

    pending = rep["counts"]["recipe_pending"]
    pend = (
        f'<div class="bar">레시피 {pending}종을 아직 못 받았다 — 상세 API 쿼터.'
        " 다음 수집 주기에 이어받는다</div>"
        if pending
        else ""
    )

    mult = rep["echo_multiplier"]
    has_inv = rep.get("has_inventory", False)
    span = 5 + has_inv + show_recipe + show_echo_craft
    body = []
    for group in rep["groups"]:
        body.append(
            f'<tr class="grp"><td colspan="{span}">'
            f"{html.escape(group['label'])}</td>"
            f'<td colspan="1" class="na">{len(group["rows"])}종</td></tr>'
        )
        for row in group["rows"]:
            # 상세는 늘 전부 보인다. 체크박스가 정하는 건 표의 열뿐이다.
            mats = _materials_table(row["normal"], "해연 제작", has_inv)
            mats += _materials_table(row["recipe"], "레시피 제작", has_inv)
            mats += _materials_table(
                row["echo_craft"].get("path"), "잔영 1개 제작", has_inv
            )
            name = html.escape(row["base_name"] or row["name"])

            # 이긴 길 한 칸만 표시한다. "가장 싼 길" 열의 색과 이어져 눈이 따라간다.
            best = (row["cheapest"] or {}).get("option")

            def cell(option, inner):
                cls = ' class="win"' if option == best else ""
                return f"<td{cls}>{inner}</td>"

            # 값 칸은 한 줄로 둔다. 상세는 아래에 따로 열려야 옆 칸이 밀리지 않는다.
            did = f"d{row['item_id']}"
            caret = '<span class="caret">▸</span> ' if mats else ""
            body.append(
                f'<tr class="row"{f" data-detail={did}" if mats else ""}>'
                + f"<td>{caret}{name}</td>"
                + cell("buy", _n(row["market"]["price"]))
                + f'<td class="na">{_n(row["market"]["count"])}</td>'
                + cell("craft", _path_cell(row["normal"], has_inv))
                + (cell("craft_oop", _oop_cell(row["normal"])) if has_inv else "")
                + (
                    f"<td>{_path_cell(row['recipe'], has_inv)}</td>"
                    if show_recipe
                    else ""
                )
                + cell("echo_buy", _echo_cell(row["echo_buy"]))
                + (
                    cell("echo_craft", _echo_cell(row["echo_craft"]))
                    if show_echo_craft
                    else ""
                )
                + f"<td>{_verdict_cell(row, mult)}</td></tr>"
            )
            if mats:
                body.append(
                    f'<tr class="detail" hidden id="{did}">'
                    f'<td colspan="{span + 1}"><div class="paths">{mats}</div></td></tr>'
                )

    def head(label, field):
        """헤더 클릭으로 정렬. 같은 열을 다시 누르면 방향이 뒤집힌다."""
        active = rep["sort"] == field
        nxt = "0" if (active and rep["desc"]) else "1"
        mark = (" ↓" if rep["desc"] else " ↑") if active else ""
        href = (
            f"?echo={mult}&amp;recipe={1 if show_recipe else 0}"
            f"&amp;sort={field}&amp;desc={nxt}"
        )
        cls = ' class="sorted"' if active else ""
        return f'<th{cls}><a href="{href}">{label}{mark}</a></th>'

    oop_head = head("실 제작", "craft_oop") if has_inv else ""
    recipe_head = head("레시피 제작", "recipe") if show_recipe else ""
    echo_craft_head = head(f"잔영×{mult} 제작", "echo_craft") if show_echo_craft else ""

    def toggle(label, field, on):
        """열 켜기·끄기. 체크하면 그 열이 표에 붙는다."""
        keep = (
            f"&amp;recipe={1 if show_recipe else 0}"
            if field != "recipe"
            else f"&amp;echo_craft={1 if show_echo_craft else 0}"
        )
        href = (
            f"?echo={mult}&amp;sort={rep['sort']}"
            f"&amp;desc={1 if rep['desc'] else 0}{keep}"
            f"&amp;{field}={0 if on else 1}"
        )
        return (
            f'<label class="toggle"><a href="{href}">'
            f'<input type="checkbox"{" checked" if on else ""} tabindex="-1">'
            f"{label}</a></label>"
        )

    toggles = (
        '<div class="toggles">'
        + toggle("레시피 제작", "recipe", show_recipe)
        + toggle(f"잔영×{mult} 제작", "echo_craft", show_echo_craft)
        + "</div>"
    )

    return f"""<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>해연 장비 원가 비교</title><style>{CSS}</style></head><body>
<h1>해연 장비 원가 비교</h1>
<div class="sub">{rep["counts"]["total"]}종 · 해연 1개를 얻는 네 가지 길 중 뭐가 싼지</div>
<ul class="intro">
<li><b>해연 1개 = 잔영 11개</b>를 감정</li>
<li>무기는 <b>다른 잔영 10개 + 내 무기 1개</b>를 까면 해연 1개</li>
<li>재료비는 <b>최저가 × 수량</b>이라 하한선 — 실제로는 이보다 비싸다</li>
<li>가장 싼 길의 <b>−금액</b>은 <b>해연 구매가</b>보다 얼마나 아끼는지</li>
</ul>
{bar}{_collector_bar(collector)}{pend}
{inv_form}
{toggles}
<div class="wrap"><table><thead><tr>
{head("아이템", "name")}{head("해연 구매", "market")}{head("매물", "count")}
{head("해연 제작", "craft")}{oop_head}{recipe_head}
{head(f"잔영×{mult} 구매", "echo_buy")}{echo_craft_head}
{head("가장 싼 길", "saving")}
</tr></thead><tbody>{"".join(body)}</tbody></table></div>
<script>{RELOAD_JS}</script>
</body></html>"""


def start_refresh(state, db_path):
    """시세 수집을 백그라운드로 돌린다. 이미 돌고 있으면 그대로 둔다.

    수집이 끝날 때까지 응답을 붙들면 화면이 얼어붙는다. 즉시 돌려주고
    진행 상태는 따로 물어보게 한다.
    """
    store = Store(db_path)
    if not state.start(expected=len(store.latest_prices())):
        return False

    def run():
        try:
            count, as_of = collect_prices(store, on_page=state.progress)
            state.done(as_of=as_of, count=count)
        except Exception as e:  # 네트워크·차단 등 — 조용히 삼키지 않는다
            state.fail(f"{type(e).__name__}: {e}")

    threading.Thread(target=run, daemon=True).start()
    return True


def make_handler(db_path, threshold_sec, state, public=False, collector=None):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if urlparse(self.path).path == "/refresh/status":
                if public:
                    return self.send_error(404)
                return self._json(state.snapshot())

            q = parse_qs(urlparse(self.path).query)
            try:
                echo = max(1, min(99, int(q.get("echo", [DEFAULT_ECHO_MULTIPLIER])[0])))
            except ValueError:
                echo = DEFAULT_ECHO_MULTIPLIER
            sort = q.get("sort", ["saving"])[0]
            desc_raw = q.get("desc", [None])[0]
            desc = None if desc_raw is None else desc_raw not in ("0", "false", "no")

            # 재고는 이 방문자의 쿠키에서만 온다. 서버는 아무것도 기억하지 않는다.
            store = Store(db_path)
            materials = store.material_index()
            owned = read_inventory_cookie(
                self.headers.get("Cookie"), set(materials.values())
            )

            # 재고를 서버에 두던 시절의 값이 남아 있으면 이 브라우저로 한 번 넘긴다.
            # 공개판에서는 하지 않는다 — 첫 방문자가 남의 재고를 가져가 버린다.
            handoff = store.take_legacy_inventory() if not owned and not public else {}
            owned = owned or handoff

            rep = build_report(
                store,
                echo_multiplier=echo,
                threshold_sec=threshold_sec,
                sort=sort,
                desc=desc,
                owned=owned,
            )

            def flag(name):
                return q.get(name, ["0"])[0] not in ("0", "false", "no")

            try:
                rejected = int(q.get("rejected", ["0"])[0])
            except ValueError:
                rejected = 0

            page = render_html(
                rep,
                show_recipe=flag("recipe"),
                show_echo_craft=flag("echo_craft"),
                materials=sorted(materials.items()),
                owned=owned,
                rejected=rejected,
                public=public,
                collector=collector.snapshot() if collector else None,
            ).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(page)))
            if handoff:
                self.send_header("Set-Cookie", inventory_cookie_header(handoff))
            self.end_headers()
            self.wfile.write(page)

        def _json(self, payload):
            body = json.dumps(payload).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            if urlparse(self.path).path == "/refresh":
                # 공개판에서는 방문자마다 원본 API를 때리면 서버 IP 하나로 몰린다.
                # 수집은 서버가 주기로 한 번만 한다.
                if public:
                    return self.send_error(404)
                started = start_refresh(state, db_path)
                return self._json({"started": started, **state.snapshot()})

            length = int(self.headers.get("Content-Length", 0))
            form = parse_qs(self.rfile.read(length).decode("utf-8"))
            owned, rejected = parse_inventory_form(
                form, set(Store(db_path).material_index().values())
            )
            self.send_response(303)
            self.send_header("Location", f"/?rejected={len(rejected)}")
            # 재고는 이 브라우저에만 남는다. 서버는 다음 요청에서 쿠키로 되받는다.
            self.send_header("Set-Cookie", inventory_cookie_header(owned))
            self.send_header("Content-Length", "0")  # 없으면 클라이언트가 끊긴다
            self.end_headers()

        def address_string(self):
            """방문자 주소. 터널 뒤라 소켓에는 늘 `127.0.0.1`만 보인다.

            진짜 IP는 Cloudflare가 `CF-Connecting-IP`에 넣어 준다. 터널 없이
            띄우면 그 헤더가 없으므로 소켓 주소로 떨어진다.
            """
            headers = getattr(self, "headers", None)
            forwarded = headers.get("CF-Connecting-IP") if headers else None
            # 이 헤더는 방문자가 아니라 Cloudflare가 넣는다. 그래도 다듬는다 —
            # 터널 없이 띄우면 아무나 위조할 수 있다.
            return log_safe(forwarded, 45) if forwarded else self.client_address[0]

        def log_message(self, fmt, *args):
            """공개판만 요청을 남긴다. 로컬은 볼 사람이 하나라 콘솔만 시끄럽다.

            User-Agent를 함께 적는다 — 이게 없으면 링크 미리보기 봇이 한꺼번에
            긁은 것과 사람이 여럿 들어온 것을 가를 수 없다.
            """
            if not public:
                return
            headers = getattr(self, "headers", None)
            agent = log_safe((headers.get("User-Agent") if headers else None) or "-")
            sys.stderr.write(
                f"{self.address_string()} [{self.log_date_time_string()}] "
                f'{log_safe(fmt % args, 300)} "{agent}"\n'
            )

    return Handler


def candle_ticks(interval=DEFAULT_INTERVAL):
    """시세를 몇 번 받을 때마다 일봉을 한 번 받을지. 하루에 한 번."""
    return max(1, 86400 // interval)


def collect_once(store, status, tick=None, candle_every=None):
    """시세 한 번. 실패해도 예외를 올리지 않고 status에 적는다.

    콘솔 로그만 남기면 방문자는 못 본다 — 페이지 상단 띠가 이 status를 읽는다.

    tick/candle_every를 주면 하루에 한 번 일봉도 받는다. 일봉은 하루 한 칸씩만
    늘어나므로 3분마다 받으면 같은 값을 18종씩 480번 긁는 꼴이다.
    """
    stamp = time.strftime("%H:%M:%S")
    try:
        n, as_of = collect_prices(store)
        status.ok()
        print(f"[{stamp}] 시세 {n}건 (기준 {as_of})", flush=True)
        ok = True
    except Exception as e:  # 네트워크·차단 등 — 조용히 삼키지 않는다
        status.failed(f"{type(e).__name__}: {e}")
        print(f"[{stamp}] 수집 실패: {type(e).__name__}: {e}", flush=True)
        ok = False

    if candle_every and tick is not None and tick % candle_every == 0:
        # 일봉은 곁다리다 — 실패해도 시세 수집을 물고 늘어지지 않는다.
        try:
            print(f"[{stamp}] 재료 {collect_candles(store)}종의 일봉", flush=True)
        except Exception as e:
            print(f"[{stamp}] 일봉 실패: {type(e).__name__}: {e}", flush=True)
    return ok


def price_loop(db_path, interval, status):
    """공개판의 시세 갱신. 방문자 대신 서버가 주기로 받는다.

    한 번 실패해도 멈추지 않는다 — 네트워크가 잠깐 끊겼다고 서버가 죽으면
    페이지 전체가 사라진다. 실패는 화면 상단 띠로 올라간다.
    """
    store = Store(db_path)
    every = candle_ticks(interval)
    tick = 0
    while True:
        collect_once(store, status, tick=tick, candle_every=every)
        tick += 1
        time.sleep(interval)


def main(argv):
    public = "--public" in argv
    args = [a for a in argv[1:] if not a.startswith("--")]
    port = int(args[0]) if args else 8765
    db = args[1] if len(args) > 1 else DEFAULT_DB
    # 공개판은 3분마다 받으므로 임계도 따라 내려온다. 30분이면 열 번 연속
    # 실패해야 경고가 뜬다 — 멈춘 걸 화면으로 알아채는 게 임계의 목적이다.
    fallback = PUBLIC_STALE_SEC if public else DEFAULT_STALE_SEC
    threshold = int(args[2]) if len(args) > 2 else fallback
    Store(db).init()

    host = "0.0.0.0" if public else "127.0.0.1"
    collector = CollectorStatus() if public else None
    if public:
        threading.Thread(
            target=price_loop, args=(db, DEFAULT_INTERVAL, collector), daemon=True
        ).start()
        print(
            f"공개판 :{port} — 새로고침 버튼 없음,"
            f" 시세는 서버가 {DEFAULT_INTERVAL // 60}분마다 받는다"
            f" (DB {db}, 신선도 임계 {threshold // 60}분)"
        )
    else:
        print(f"http://localhost:{port}  (DB {db}, 신선도 임계 {threshold // 60}분)")

    handler = make_handler(
        db, threshold, RefreshState(), public=public, collector=collector
    )
    # 수집이 도는 동안에도 진행 상태를 물어볼 수 있어야 한다
    ThreadingHTTPServer((host, port), handler).serve_forever()


if __name__ == "__main__":
    sys.exit(main(sys.argv))
