#!/usr/bin/env python3
"""로컬 비교 페이지.

    python3 serve.py [포트] [DB경로] [신선도임계초]

원가는 전부 `최저가 × 수량`이라 하한선이다. 페이지가 그 사실을 숨기지 않는다.
"""

import html
import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from collect import collect_prices
from classify import group_materials
from cost import DEFAULT_ECHO_MULTIPLIER, DEFAULT_STALE_SEC
from inventory import parse_inventory_form
from refresh import RefreshState
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
.matgrid { display:grid; gap:8px 14px;
  grid-template-columns:repeat(auto-fill,minmax(190px,1fr)); }
.matinput { display:flex; justify-content:space-between; align-items:center;
  gap:8px; font-size:13px; }
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


def _inventory_form(materials, owned, rejected=0):
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
            f'<label class="matinput">{html.escape(name)}'
            f'<input type="number" name="qty_{kind_id}" min="0" step="1"'
            f' value="{owned.get(kind_id, 0)}"></label>'
            for name, kind_id in g["items"]
        )
        + "</div></div>"
        for g in group_materials(materials)
    )
    held = sum(1 for _, k in materials if owned.get(k))
    summary = f"가진 재료 ({held}종 입력됨)" if held else "가진 재료"
    return (
        # 늘 접힌 채로 연다. 열 체크박스를 눌러 페이지가 갱신될 때마다 펼쳐지면
        # 표가 아래로 밀려 눌린 곳을 다시 찾아야 한다.
        '<details class="inv">'
        f"<summary>{summary}</summary>"
        f'{warn}<form method="post" action="/inventory">'
        f"{cells}"
        '<p><button type="submit">저장</button> '
        '<button id="clear-inv" type="button">모두 비우기</button>'
        ' <span class="na">비우기는 칸만 0으로 채운다 — 저장을 눌러야 반영된다</span></p>'
        "</form></details>"
    )


def render_html(
    rep, show_recipe=False, show_echo_craft=False, materials=(), owned=None, rejected=0
):
    inv_form = _inventory_form(materials, owned or {}, rejected)
    f = rep["freshness"]
    if f is None:
        bar = '<div class="bar stale">시세를 아직 한 번도 받지 못했다</div>'
    else:
        mins = f["age_sec"] // 60
        cls = "bar stale" if f["stale"] else "bar"
        msg = f"시세 기준 {html.escape(str(f['as_of']))} · {mins}분 전" + (
            f" — 임계 {f['threshold_sec'] // 60}분을 넘었다. 수집기가 멈췄는지 확인할 것"
            if f["stale"]
            else ""
        )
        bar = (
            f'<div class="{cls}"><span>{msg}</span>'
            '<button id="reload" type="button">새로고침</button>'
            '<span id="prog"><span id="track"><span id="fill"></span></span>'
            '<span id="ptext"></span></span>'
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
</ul>
{bar}{pend}
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


def make_handler(db_path, threshold_sec, state):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if urlparse(self.path).path == "/refresh/status":
                return self._json(state.snapshot())

            q = parse_qs(urlparse(self.path).query)
            try:
                echo = max(1, min(99, int(q.get("echo", [DEFAULT_ECHO_MULTIPLIER])[0])))
            except ValueError:
                echo = DEFAULT_ECHO_MULTIPLIER
            sort = q.get("sort", ["saving"])[0]
            desc_raw = q.get("desc", [None])[0]
            desc = None if desc_raw is None else desc_raw not in ("0", "false", "no")
            rep = build_report(
                Store(db_path),
                echo_multiplier=echo,
                threshold_sec=threshold_sec,
                sort=sort,
                desc=desc,
            )

            def flag(name):
                return q.get(name, ["0"])[0] not in ("0", "false", "no")

            show_recipe = flag("recipe")
            show_echo_craft = flag("echo_craft")

            store = Store(db_path)
            try:
                rejected = int(q.get("rejected", ["0"])[0])
            except ValueError:
                rejected = 0

            page = render_html(
                rep,
                show_recipe=show_recipe,
                show_echo_craft=show_echo_craft,
                materials=sorted(store.material_index().items()),
                owned=store.inventory(),
                rejected=rejected,
            ).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(page)))
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
                started = start_refresh(state, db_path)
                return self._json({"started": started, **state.snapshot()})

            length = int(self.headers.get("Content-Length", 0))
            form = parse_qs(self.rfile.read(length).decode("utf-8"))
            store = Store(db_path)
            owned, rejected = parse_inventory_form(
                form, set(store.material_index().values())
            )
            store.save_inventory(owned)
            self.send_response(303)
            self.send_header("Location", f"/?rejected={len(rejected)}")
            self.send_header("Content-Length", "0")  # 없으면 클라이언트가 끊긴다
            self.end_headers()

        def log_message(self, *a):
            pass

    return Handler


def main(argv):
    port = int(argv[1]) if len(argv) > 1 else 8765
    db = argv[2] if len(argv) > 2 else DEFAULT_DB
    threshold = int(argv[3]) if len(argv) > 3 else DEFAULT_STALE_SEC
    Store(db).init()
    print(f"http://localhost:{port}  (DB {db}, 신선도 임계 {threshold // 60}분)")
    handler = make_handler(db, threshold, RefreshState())
    # 수집이 도는 동안에도 진행 상태를 물어볼 수 있어야 한다
    ThreadingHTTPServer(("127.0.0.1", port), handler).serve_forever()


if __name__ == "__main__":
    sys.exit(main(sys.argv))
