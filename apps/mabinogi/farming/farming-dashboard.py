#!/usr/bin/env python3
"""영혼석 파밍 대시보드 — 어느 던전이 시간당 데카로 이득인가.

    farming-dashboard.py            서버 뜨고 브라우저 열림
    farming-dashboard.py --port N   포트 지정 (기본 8765)
    farming-dashboard.py --no-browser

집계는 analyze-logs.py의 soul_dungeon_ranking·daily_summary·daily_soul_deca를
그대로 쓴다. 여기서 새로 세지 않는다 — 터미널과 웹의 숫자가 갈리지 않게.
새로고침마다 로그·시세를 다시 읽으므로, 앱이 돌면 최신 판까지 반영된다.

시세는 equipment-cost 저장소를 읽기 전용으로 가져온다(경로는 shared/mabi/data.py가
해석). 없거나 낡으면 데카 열을 비우고 개수만 보이며 갱신 시각을 띄운다.
"""

import argparse
import importlib.util
import json
import pathlib
import urllib.parse
import webbrowser
from collections import Counter
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# 파일명이 하이픈이라 일반 import가 안 된다. 경로로 로드한다.
_spec = importlib.util.spec_from_file_location(
    "analyze_logs", pathlib.Path(__file__).with_name("analyze-logs.py")
)
analyze = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(analyze)


def build_payload(directory, day=None):
    """로그·시세를 다시 읽어 영혼석 순위 페이로드를 만든다. 읽기 실패는 0판이
    아니라 오류로 표시한다 — 앱이 멈춰도 페이지가 어제 숫자를 멀쩡히 보여주면
    안 된다.

    day("MM/DD", KST)가 오면 순위·기타 집계는 그날 판만 본다. 단 활동량 차트용
    daily·deca_trend는 항상 전체 기간(시간 네비게이터라서)."""
    path = pathlib.Path(directory).expanduser() / "cycle-log.jsonl"
    error = None
    cycles = []
    if not path.exists():
        error = f"로그 파일이 없다: {path}"
    else:
        try:
            cycles = analyze.read_jsonl(path)
        except OSError as exc:
            error = f"로그를 못 읽었다: {exc}"

    corrections = analyze.load_corrections()  # 매 요청 재로드 — 편집 즉시 반영
    whitelist = analyze.load_soul_whitelist(corrections)
    markers = analyze.load_paid_markers(corrections)
    prices, price_as_of = analyze.read_soul_prices(whitelist)

    # 순위는 날짜 필터가 걸리면 그날 판만. 차트는 전체 기간 그대로.
    rank_cycles = cycles
    if day:
        rank_cycles = [
            c for c in cycles if analyze.kst(c["at"]).strftime("%m/%d") == day
        ]

    # 전체·재화·무료 세 벌. gph는 셋이 던전 전체 판 기준으로 공유한다.
    rank = {
        m: analyze.soul_dungeon_ranking(
            rank_cycles, whitelist, prices, corrections, mode=m, markers=markers
        )
        for m in ("all", "paid", "free")
    }
    paid_games = sum(1 for c in rank_cycles if analyze.run_mode(c, markers) == "재화")

    # 진단(#1): 어느 원문도 조용히 안 버린다. 기타 던전으로 묶인 raw 던전명도.
    misc_dungeons = Counter()
    for c in cycles:
        raw = c.get("dungeon")
        if raw and analyze.canonical_dungeon(raw) == "기타 던전":
            misc_dungeons[analyze.normalize_dungeon(raw)] += 1

    # 헤더 총 판수는 항상 전체 기간(날짜 필터와 무관).
    stamps = sorted(c["at"] for c in cycles)
    full_period = {
        "start": stamps[0] if stamps else None,
        "last": stamps[-1] if stamps else None,
        "total_games": len(cycles),
    }

    return {
        "rows": rank["all"]["rows"],
        "rows_paid": rank["paid"]["rows"],
        "rows_free": rank["free"]["rows"],
        "other_count": rank["all"]["other_count"],
        "unknown_count": rank["all"]["unknown_count"],
        "other_items": rank["all"]["other_items"],  # 진단: 기타 원문 → 건수
        "unknown_items": rank["all"]["unknown_items"],  # 진단: 종류 불명 원문
        "misc_dungeons": dict(misc_dungeons.most_common()),  # 진단: 기타 던전 raw
        "period": full_period,
        "selected_day": day,  # 날짜 필터(MM/DD) | None
        "day_games": len(rank_cycles) if day else None,
        "paid_games": paid_games,  # 재화 판수(표본 얇음 안내용)
        "daily": analyze.daily_summary(cycles),
        "deca_trend": analyze.daily_soul_deca(cycles, whitelist, prices, markers),
        "whitelist": whitelist,  # {어간: 캐논 이름} — 칩 순서·이름
        "prices": prices,  # {캐논 이름: 데카}
        "price_as_of": price_as_of,  # ISO | None
        "min_samples": analyze.MIN_SAMPLES,
        "log_error": error,
        "corrections_path": str(analyze.CORRECTIONS_PATH),
    }


def build_records(directory):
    """모든 판을 개별 레코드로. 시각·던전(raw·정규화)·재화/무료·슬롯별 분류를
    담아 '전체 데이터 개별 보기'에 쓴다. 최신 판이 위로 오게 뒤집는다."""
    path = pathlib.Path(directory).expanduser() / "cycle-log.jsonl"
    cycles = analyze.read_jsonl(path) if path.exists() else []
    corrections = analyze.load_corrections()
    whitelist = analyze.load_soul_whitelist(corrections)
    markers = analyze.load_paid_markers(corrections)
    split_map = corrections.get("분리", {})

    out = []
    for idx, c in enumerate(cycles):
        items = []
        for slot in c.get("items", []) or []:
            for part in analyze.split_slot(slot, split_map):
                kind, stem = analyze.match_soul_stone(part, whitelist)
                if kind == "soul":
                    tag = "영혼석·" + stem
                elif kind == "unknown":
                    tag = "종류불명"
                else:
                    itemkind, _n = analyze.classify_slot(part, corrections)
                    tag = "기타" if itemkind == "item" else "제외"
                items.append({"raw": part, "tag": tag})
        out.append(
            {
                "idx": idx,  # 원본 로그 줄 번호(개별 수정용)
                "at": c.get("at"),
                "dungeon": c.get("dungeon"),
                "canon": analyze.canonical_dungeon(c.get("dungeon")),
                "entry": c.get("entry"),
                "mode": analyze.run_mode(c, markers),  # 오버라이드 우선, 없으면 표식
                "mode_forced": c.get("mode") in ("재화", "무료"),  # 사람이 못박았나
                "record": c,  # 전체 레코드(다 편집 가능하게)
                "items": items,
            }
        )
    out.reverse()  # 최신 판이 위로
    return out


def edit_record(directory, idx, record):
    """개별 판(로그 한 줄)을 통째로 교체한다 — 모든 필드 편집 가능. record는
    반드시 dict이고 "at"(시각)을 가져야 한다(다른 판과 안 뒤섞이게). 원본은
    .jsonl.bak 백업 후 전체를 다시 쓴다. 봇이 도는 중엔 append와 겹칠 수 있어
    멈추고 쓰길 권한다(백업이 있으니 되돌릴 순 있다)."""
    if not isinstance(record, dict) or not record.get("at"):
        raise ValueError("레코드가 dict가 아니거나 at(시각)이 없다")
    path = pathlib.Path(directory).expanduser() / "cycle-log.jsonl"
    cycles = analyze.read_jsonl(path)
    if not 0 <= idx < len(cycles):
        raise IndexError("판 번호 범위 밖")
    cycles[idx] = record
    backup = path.with_suffix(".jsonl.bak")
    backup.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
    lines = [json.dumps(c, ensure_ascii=False) for c in cycles]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_dungeon(directory, name):
    """한 던전(canonical 이름)의 상세 데이터. 없으면 None."""
    path = pathlib.Path(directory).expanduser() / "cycle-log.jsonl"
    cycles = analyze.read_jsonl(path) if path.exists() else []
    corrections = analyze.load_corrections()
    whitelist = analyze.load_soul_whitelist(corrections)
    markers = analyze.load_paid_markers(corrections)
    prices, _ = analyze.read_soul_prices(whitelist)
    return analyze.dungeon_detail(cycles, name, whitelist, prices, corrections, markers)


def save_corrections_text(text):
    """교정 JSON 텍스트를 검증 후 저장한다. 원본은 .json.bak으로 백업.
    잘못된 JSON이면 ValueError를 던져 저장하지 않는다."""
    json.loads(text)  # 깨진 JSON이면 여기서 멈춘다 — 원본 안 건드림
    path = analyze.CORRECTIONS_PATH
    backup = path.with_suffix(".json.bak")
    if path.exists():
        backup.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
    path.write_text(text, encoding="utf-8")


# 영혼석 다섯 정수의 색. 도메인의 시그니처 — 칩·행 색점·인라인 막대에 관통한다.
# 망령(창백한 청록)·야생(흙빛 올리브)·공명(보랏빛)·원념(짙은 크림슨)·파동(청색).
PAGE = r"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>영혼석 원장</title>
<style>
  :root {
    /* 웜 스톤 차콜 — 던전 내부의 어둠. 같은 색조에서 명도만 올린다. */
    --bg: #14110d;
    --s1: #1b1712;     /* 패널·행 */
    --s2: #241f18;     /* hover·떠오른 면 */
    --inset: #0f0c08;  /* 막대 트랙·입력 */
    --border: rgba(233,216,180,.09);
    --border-soft: rgba(233,216,180,.05);
    --border-strong: rgba(233,216,180,.18);
    /* 웜 오프화이트 → 웜 그레이. 네 단계. */
    --fg: #f1eadb;
    --fg2: #c6bba6;
    --fg3: #8d8474;
    --fg-muted: #5e5749;
    /* 데카 = 거래소 화폐. 돈 지표는 웜 골드로 빛난다. */
    --deca: #e8b84b;
    --deca-dim: rgba(232,184,75,.16);
    --warn-c: #e6b45c;
    --err-c: #e2685f;
    /* 영혼석별 색 */
    --st-망령: #5fd0bd;
    --st-야생: #a6c46a;
    --st-공명: #b294e8;
    --st-원념: #e2685f;
    --st-파동: #5ea8e8;
    --radius: 10px;
    --radius-sm: 6px;
    color-scheme: dark;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0; background: var(--bg); color: var(--fg);
    font: 15px/1.5 system-ui, -apple-system, "Apple SD Gothic Neo", sans-serif;
    -webkit-font-smoothing: antialiased;
  }
  .num { font-family: ui-monospace, "SF Mono", Menlo, monospace;
         font-variant-numeric: tabular-nums; }

  /* ── 원장 헤더(상태바) ── */
  header {
    display: flex; flex-wrap: wrap; align-items: center; gap: 10px 22px;
    padding: 14px 24px; background: var(--s1);
    border-bottom: 1px solid var(--border);
  }
  .brand { display: flex; flex-direction: column; margin-right: 6px; }
  .brand .t { font-size: 17px; font-weight: 700; letter-spacing: -.01em; }
  .brand .sub { font-size: 12px; color: var(--fg3); }
  .stat { display: flex; flex-direction: column; gap: 1px; }
  .stat .k { font-size: 11px; color: var(--fg3); letter-spacing: .02em; }
  .stat .v { font-size: 14px; color: var(--fg); font-weight: 600; }
  .stat .v.warn { color: var(--warn-c); }
  .stat .v.err { color: var(--err-c); }
  .stat .v.ok { color: var(--st-야생); }
  .dot { display: inline-block; width: 7px; height: 7px; border-radius: 50%;
         margin-right: 5px; vertical-align: middle; }
  .spacer { margin-left: auto; }
  button.refresh {
    background: transparent; color: var(--deca);
    border: 1px solid var(--border-strong); border-radius: var(--radius-sm);
    padding: 7px 15px; font-size: 13px; font-weight: 600; cursor: pointer;
    transition: background .12s ease, border-color .12s ease;
  }
  button.refresh:hover { background: var(--deca-dim); border-color: var(--deca); }
  button.refresh:active { transform: translateY(1px); }

  .errbar {
    margin: 0; padding: 10px 24px; background: rgba(226,104,95,.12);
    border-bottom: 1px solid rgba(226,104,95,.3); color: var(--err-c);
    font-size: 13px; display: none;
  }
  .errbar.show { display: block; }

  main { max-width: 1100px; margin: 0 auto; padding: 22px 24px 60px; }

  /* ── 컨트롤: 영혼석 칩 + 지표 토글 ── */
  .controls {
    display: flex; flex-wrap: wrap; align-items: center; gap: 12px;
    margin-bottom: 18px;
  }
  .chips { display: flex; flex-wrap: wrap; gap: 7px; }
  .chip {
    display: inline-flex; align-items: center; gap: 7px;
    padding: 6px 13px 6px 11px; border-radius: 999px;
    background: var(--s1); border: 1px solid var(--border);
    color: var(--fg2); font-size: 13px; font-weight: 600; cursor: pointer;
    transition: background .12s, border-color .12s, color .12s;
  }
  .chip:hover { background: var(--s2); color: var(--fg); }
  .chip .cdot { width: 9px; height: 9px; border-radius: 50%; }
  .chip.active { color: var(--fg); border-color: var(--border-strong); }
  .chip.active[data-stem] { background: color-mix(in oklab, var(--stem-c) 22%, var(--s1)); }
  .chip.all.active { background: var(--s2); border-color: var(--border-strong); }
  .chip .cnt { color: var(--fg3); font-weight: 500; }

  .toggle { display: flex; margin-left: auto; background: var(--inset);
            border: 1px solid var(--border); border-radius: var(--radius-sm);
            padding: 3px; gap: 2px; }
  .toggle button {
    background: transparent; border: 0; color: var(--fg3);
    padding: 6px 14px; font-size: 13px; font-weight: 600; cursor: pointer;
    border-radius: 4px; transition: background .12s, color .12s;
  }
  .toggle button.on { background: var(--s2); color: var(--fg); }
  .toggle button.on[data-metric="deca"] { color: var(--deca); }

  /* ── 순위표 ── */
  .panel { background: var(--s1); border: 1px solid var(--border);
           border-radius: var(--radius); overflow: hidden; }
  table { border-collapse: collapse; width: 100%; }
  thead th {
    font-size: 11px; font-weight: 600; color: var(--fg3); text-align: right;
    padding: 11px 14px; border-bottom: 1px solid var(--border);
    letter-spacing: .03em; white-space: nowrap;
  }
  thead th:first-child { text-align: left; }
  thead th.hero { color: var(--deca); }
  tbody td { padding: 11px 14px; border-bottom: 1px solid var(--border-soft);
             text-align: right; white-space: nowrap; }
  tbody tr:last-child td { border-bottom: 0; }
  tbody tr:hover { background: var(--s2); }
  tr.rank-row { cursor: pointer; }
  td.dungeon { text-align: left; }
  .dcell { display: flex; align-items: center; gap: 9px; }
  .dcell .sdot { width: 9px; height: 9px; border-radius: 50%; flex: none; }
  .dcell .dn { font-weight: 600; color: var(--fg); }
  .est { color: var(--warn-c); font-size: 11px; margin-left: 3px; }
  .stone { font-weight: 600; }
  .price { color: var(--fg2); }
  .muted { color: var(--fg-muted); }

  /* 히어로 막대 셀 — 원장의 저울. 길이 = 1위 대비 상대값. */
  .bar { position: relative; min-width: 190px; }
  .bar .track { position: absolute; inset: 6px 14px; border-radius: 4px; }
  .bar .fill { position: absolute; left: 14px; top: 6px; bottom: 6px;
               border-radius: 4px; }
  .bar .lab { position: relative; z-index: 1; padding-right: 2px;
              font-weight: 700; }
  .bar.deca .lab { color: var(--deca); }
  .bar .sub2 { color: var(--fg3); font-weight: 500; font-size: 12px; }
  td.dim { color: var(--fg3); }

  .section { font-size: 13px; font-weight: 700; color: var(--fg2);
             margin: 30px 0 4px; letter-spacing: .02em; }
  .note { color: var(--fg3); font-size: 12px; margin: 2px 0 12px; }
  .note code { color: var(--warn-c); }

  /* 진단 패널(#1): 조용히 버린 원문을 다 펼쳐 본다 → 교정하러 간다 */
  .stat.clickable { cursor: pointer; }
  .stat.clickable:hover .k { color: var(--fg2); }
  #diag { display: none; margin: 0 24px 4px; background: var(--s1);
          border: 1px solid var(--border); border-radius: var(--radius);
          padding: 14px 18px; }
  #diag.open { display: block; }
  #diag .dhead { display: flex; justify-content: space-between; align-items: baseline;
                 margin-bottom: 10px; }
  #diag .dhead .path { color: var(--fg3); font-size: 12px; }
  #diag .dhead .path code { color: var(--warn-c); }
  #diag .cols { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; }
  #diag .col h4 { margin: 0 0 6px; font-size: 12px; color: var(--fg2);
                  font-weight: 700; }
  #diag .col .list { max-height: 240px; overflow: auto; font-size: 13px; }
  #diag .col .list div { display: flex; justify-content: space-between; gap: 10px;
                         padding: 2px 0; border-bottom: 1px solid var(--border-soft); }
  #diag .col .list .nm { color: var(--fg2); overflow: hidden; text-overflow: ellipsis;
                         white-space: nowrap; }
  #diag .col .list .c { color: var(--fg3); flex: none; }
  #diag .col .empty2 { color: var(--fg-muted); font-size: 12px; }
  @media (max-width: 760px) { #diag .cols { grid-template-columns: 1fr; } }

  /* 활동량 차트 */
  .chart { background: var(--s1); border: 1px solid var(--border);
           border-radius: var(--radius); padding: 16px 18px; }
  .chart svg { display: block; width: 100%; height: auto; }
  .legend { display: flex; gap: 16px; margin-top: 8px; font-size: 12px;
            color: var(--fg3); }
  .legend .k { display: inline-flex; align-items: center; gap: 6px; }
  .legend .swatch { width: 12px; height: 3px; border-radius: 2px; }
  .empty { color: var(--fg-muted); padding: 40px 14px; text-align: center; }

  /* 전체 데이터 브라우저 */
  .rec-controls { display: flex; align-items: center; gap: 12px; margin-bottom: 8px; }
  #rec-search { flex: 1; max-width: 420px; background: var(--inset);
                border: 1px solid var(--border); border-radius: var(--radius-sm);
                color: var(--fg); padding: 8px 12px; font: inherit; }
  #rec-search:focus { outline: none; border-color: var(--border-strong); }
  #records { overflow-x: auto; background: var(--s1); border: 1px solid var(--border);
             border-radius: var(--radius); }
  #records table { border-collapse: collapse; width: 100%; }
  #records th { position: sticky; top: 0; background: var(--s2); z-index: 1;
                font-size: 11px; color: var(--fg3); text-align: left; font-weight: 600;
                padding: 8px 12px; border-bottom: 1px solid var(--border); }
  #records td { padding: 8px 12px; border-bottom: 1px solid var(--border-soft);
                vertical-align: top; }
  #records tbody tr { cursor: pointer; }
  #records tbody tr:hover { background: var(--s2); }
  #records td.items-cell { white-space: normal; line-height: 1.9; }
  #records td.at { color: var(--fg3); white-space: nowrap; }
  #records td.dg { color: var(--fg); white-space: nowrap; }
  #records td.dg .raw { color: var(--fg-muted); font-size: 11px; }
  #records .mtag { font-size: 11px; padding: 1px 7px; border-radius: 10px;
                   white-space: nowrap; }
  #records .mtag.재화 { background: var(--deca-dim); color: var(--deca); }
  #records .mtag.무료 { background: var(--s2); color: var(--fg3); }
  #records .it { display: inline-block; margin: 1px 4px 1px 0; font-size: 12px;
                 padding: 1px 6px; border-radius: 4px; background: var(--inset); }
  #records .it.soul { color: var(--deca); }
  #records .it.기타 { color: var(--fg2); }
  #records .it.종류불명 { color: var(--warn-c); }
  #records .it.제외 { color: var(--fg-muted); }

  /* 교정 편집기 */
  .editor textarea { width: 100%; min-height: 300px; resize: vertical;
                     background: var(--inset); border: 1px solid var(--border);
                     border-radius: var(--radius); color: var(--fg);
                     font-family: ui-monospace, monospace; font-size: 13px;
                     line-height: 1.5; padding: 14px; }
  .editor textarea:focus { outline: none; border-color: var(--border-strong); }
  .editor-bar { display: flex; align-items: center; gap: 14px; margin-top: 10px; }
  button.save { background: var(--deca); color: #1a1400; border: 0;
                border-radius: var(--radius-sm); padding: 8px 18px; font-size: 13px;
                font-weight: 700; cursor: pointer; }
  button.save:active { transform: translateY(1px); }
  .ed-status { font-size: 13px; }
  .ed-status.ok { color: var(--st-야생); }
  .ed-status.err { color: var(--err-c); }

  /* 탭 */
  .tabs { display: flex; gap: 2px; border-bottom: 1px solid var(--border);
          margin-bottom: 18px; }
  .tabs button { background: transparent; border: 0; border-bottom: 2px solid transparent;
                 color: var(--fg3); padding: 10px 18px; font-size: 14px; font-weight: 600;
                 cursor: pointer; margin-bottom: -1px; }
  .tabs button:hover { color: var(--fg2); }
  .tabs button.on { color: var(--fg); border-bottom-color: var(--deca); }

  /* 날짜 필터 안내바 */
  #day-bar { display: none; align-items: center; gap: 10px; margin-bottom: 14px;
             padding: 9px 14px; background: var(--deca-dim);
             border: 1px solid var(--border-strong); border-radius: var(--radius-sm);
             font-size: 13px; color: var(--fg); }
  #day-bar b { color: var(--deca); }
  #day-bar button { margin-left: auto; background: transparent; color: var(--fg2);
                    border: 1px solid var(--border-strong); border-radius: var(--radius-sm);
                    padding: 4px 12px; font-size: 12px; cursor: pointer; }
  #day-bar button:hover { background: var(--s2); color: var(--fg); }

  /* 오버레이(던전 상세·개별 수정) */
  #detail-overlay, #edit-overlay { position: fixed; inset: 0; z-index: 50;
    background: rgba(0,0,0,.6); display: none; overflow: auto; padding: 36px 16px; }
  #detail-overlay.open, #edit-overlay.open { display: block; }
  #detail-panel { max-width: 920px; margin: 0 auto; background: var(--s1);
    border: 1px solid var(--border-strong); border-radius: var(--radius); padding: 22px 26px; }
  #edit-panel { max-width: 620px; margin: 0 auto; background: var(--s1);
    border: 1px solid var(--border-strong); border-radius: var(--radius); padding: 22px 26px; }
  .dt-head { display: flex; justify-content: space-between; align-items: flex-start;
             gap: 12px; margin-bottom: 6px; }
  .dt-head .dt-title { font-size: 18px; font-weight: 700; }
  .dt-head .dt-sub { color: var(--fg3); font-size: 12px; margin-top: 2px; }
  .dt-close { background: transparent; border: 1px solid var(--border-strong);
              color: var(--fg2); border-radius: var(--radius-sm); padding: 5px 12px;
              cursor: pointer; font-size: 13px; flex: none; }
  .dt-tiles { display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
              gap: 10px; margin: 16px 0; }
  .dt-tile { background: var(--inset); border: 1px solid var(--border);
             border-radius: var(--radius-sm); padding: 10px 12px; }
  .dt-tile .tl { font-size: 11px; color: var(--fg3); }
  .dt-tile .tv { font-size: 17px; font-weight: 700; margin-top: 3px; }
  .dt-tile .tv.deca { color: var(--deca); }
  .dt-sec { font-size: 13px; font-weight: 700; color: var(--fg2); margin: 20px 0 8px; }
  .dt-two { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
  .dt-mini { background: var(--inset); border: 1px solid var(--border);
             border-radius: var(--radius-sm); padding: 12px 14px; }
  .dt-mini h5 { margin: 0 0 6px; font-size: 12px; color: var(--fg2); }
  .dt-mini .row { display: flex; justify-content: space-between; font-size: 13px;
                  padding: 2px 0; }
  .dt-mini .row .lb { color: var(--fg3); }
  .dt-list { max-height: 200px; overflow: auto; font-size: 13px; }
  .dt-list .row { display: flex; justify-content: space-between; padding: 2px 0;
                  border-bottom: 1px solid var(--border-soft); }
  .dt-list .row .lb { color: var(--fg2); overflow: hidden; text-overflow: ellipsis;
                      white-space: nowrap; }
  .dt-chart svg { display: block; width: 100%; height: auto; }
  @media (max-width: 700px) { .dt-two { grid-template-columns: 1fr; } }

  /* 개별 수정 폼 */
  .ed-field { margin-bottom: 14px; }
  .ed-field label { display: block; font-size: 12px; color: var(--fg3); margin-bottom: 4px; }
  .ed-field input, .ed-field textarea { width: 100%; background: var(--inset);
    border: 1px solid var(--border); border-radius: var(--radius-sm); color: var(--fg);
    font: inherit; padding: 8px 10px; }
  .ed-field textarea { min-height: 120px; font-family: ui-monospace, monospace;
    font-size: 13px; resize: vertical; }
  .ed-field .hint { color: var(--fg-muted); font-size: 11px; margin-top: 3px; }
</style>
</head>
<body>
<header>
  <div class="brand">
    <span class="t">영혼석 원장</span>
    <span class="sub">어느 던전이 시간당 데카로 이득인가</span>
  </div>
  <div class="stat"><span class="k">마지막 기록</span><span class="v num" id="last">–</span></div>
  <div class="stat"><span class="k">총 판수</span><span class="v num" id="total">–</span></div>
  <div class="stat"><span class="k">시세 갱신</span><span class="v num" id="price-at">–</span></div>
  <div class="stat clickable" id="stat-other" title="클릭 → 원문 진단">
    <span class="k">기타(미집계) ▾</span><span class="v num" id="other">–</span></div>
  <div class="stat clickable" id="stat-unknown" title="클릭 → 원문 진단">
    <span class="k">종류 불명 ▾</span><span class="v num" id="unknown">–</span></div>
  <div class="spacer"></div>
  <button class="refresh" id="refresh">새로고침</button>
</header>
<div class="errbar" id="errbar"></div>
<div id="diag"></div>

<main>
  <div class="tabs" id="tabs">
    <button data-tab="rank" class="on">순위</button>
    <button data-tab="records">전체 데이터</button>
    <button data-tab="edit">교정 사전</button>
  </div>
  <div id="day-bar"></div>

  <section id="pane-rank">
    <div class="controls">
      <div class="chips" id="chips"></div>
      <div class="toggle" id="mode">
        <button data-mode="all" class="on">전체</button>
        <button data-mode="paid">재화 씀</button>
        <button data-mode="free">무료</button>
      </div>
      <div class="toggle" id="toggle">
        <button data-metric="deca" class="on">시간당 데카</button>
        <button data-metric="count">시간당 개수</button>
      </div>
    </div>
    <div class="note" id="mode-note"></div>
    <div class="note">던전 행을 누르면 상세(언제 돌렸나·날짜별 드랍률·재화무료·전리품)가 열린다.</div>

    <div id="ranking"></div>

    <div class="section">활동량 — 날짜별 데카와 얼마나 돌렸나</div>
    <div class="controls" style="margin-bottom:10px">
      <div class="toggle" id="chart-bar">
        <button data-cb="deca_total" class="on">총 데카</button>
        <button data-cb="active_hours">가동 시간</button>
        <button data-cb="games">판수</button>
      </div>
      <span class="note" style="margin:0">막대 = 선택 지표 · <span style="color:var(--deca)">금색 선 = 시간당 데카</span> · 위 회색 숫자 = 판수</span>
    </div>
    <div class="chart" id="chart"></div>
  </section>

  <section id="pane-records" hidden>
    <div class="note">모든 판을 최신순으로(시간=한국시간). 검색으로 던전·아이템·재화 여부를 좁힌다. 아이템 색: <span style="color:var(--deca)">영혼석</span> · <span style="color:var(--fg2)">기타</span> · <span style="color:var(--warn-c)">종류불명</span> · <span style="color:var(--fg-muted)">제외</span>. 판을 누르면 그 판을 개별 수정한다.</div>
    <div class="rec-controls">
      <input id="rec-search" placeholder="검색: 던전·아이템·재화·무료 (예: 피오드 파편)" />
      <span class="note" id="rec-count"></span>
    </div>
    <div id="records"></div>
  </section>

  <section id="pane-edit" hidden>
    <div class="note">OCR 오독·제외·분리·영혼석 어간·재화 표식은 <b>패턴 단위</b>로 여기서 고친다(개별 판이 아니라 규칙 — 개별 판은 전체 데이터 탭에서). 저장하면 원본은 <code>.json.bak</code>으로 백업되고 전체 판에 다시 적용된다.</div>
    <div class="editor">
      <textarea id="corr-text" spellcheck="false"></textarea>
      <div class="editor-bar">
        <button class="save" id="corr-save">저장 후 재적용</button>
        <span id="corr-status" class="ed-status"></span>
      </div>
    </div>
  </section>
</main>

<div id="detail-overlay"><div id="detail-panel"></div></div>
<div id="edit-overlay"><div id="edit-panel"></div></div>

<script>
const $ = (id) => document.getElementById(id);
const STONE = { "망령": "#5fd0bd", "야생": "#a6c46a", "공명": "#b294e8",
                "원념": "#e2685f", "파동": "#5ea8e8" };
let DATA = null, METRIC = "deca", MODE = "all", FILTER = null, MIN = 20;
let CHART_BAR = "deca_total";  // 활동량 막대 지표
let DAY = null;  // 날짜 필터(MM/DD) — 순위·전체 데이터를 그날로 좁힌다

function esc(s) {
  return String(s).replace(/[&<>"]/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
}
function fmt(n, d = 0) {
  if (n === null || n === undefined) return "–";
  return n.toLocaleString("ko-KR", { minimumFractionDigits: d, maximumFractionDigits: d });
}
function shortTime(iso) {
  if (!iso) return "–";
  return new Date(iso).toLocaleString("ko-KR", { timeZone: "Asia/Seoul",
    month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" });
}

// ── 헤더 ──
function renderHeader(d) {
  $("last").textContent = shortTime(d.period.last);
  $("total").textContent = fmt(d.period.total_games || 0);
  $("other").textContent = fmt(d.other_count || 0);
  $("unknown").textContent = fmt(d.unknown_count || 0);
  $("other").className = "v num" + ((d.other_count || 0) > 0 ? " warn" : "");
  $("unknown").className = "v num" + ((d.unknown_count || 0) > 0 ? " warn" : "");

  const pa = $("price-at");
  if (!d.price_as_of) {
    pa.innerHTML = '<span class="dot" style="background:var(--err-c)"></span>시세 없음';
    pa.className = "v num err";
  } else {
    const ageH = (Date.now() - new Date(d.price_as_of)) / 3.6e6;
    const stale = ageH > 2;
    const color = stale ? "var(--warn-c)" : "var(--st-야생)";
    pa.innerHTML = '<span class="dot" style="background:' + color + '"></span>' +
      shortTime(d.price_as_of) + (stale ? " 낡음" : "");
    pa.className = "v num" + (stale ? " warn" : " ok");
  }

  const err = $("errbar");
  if (d.log_error) { err.classList.add("show"); err.textContent = "오류: " + d.log_error; }
  else err.classList.remove("show");
}

// ── 영혼석 칩 ──
function stemCounts(d) {
  const c = {};
  for (const r of (d[ROWSET[MODE]] || d.rows)) c[r.stem] = (c[r.stem] || 0) + r.count_total;
  return c;
}
function renderChips(d) {
  const counts = stemCounts(d);
  const stems = Object.keys(d.whitelist || {});
  const box = $("chips");
  let html = '<div class="chip all' + (FILTER === null ? " active" : "") +
    '" data-f="">전체</div>';
  for (const stem of stems) {
    const col = STONE[stem] || "var(--fg3)";
    const active = FILTER === stem ? " active" : "";
    const priced = (d.prices || {})[d.whitelist[stem]] != null;
    html += '<div class="chip' + active + '" data-f="' + esc(stem) +
      '" data-stem="1" style="--stem-c:' + col + '">' +
      '<span class="cdot" style="background:' + col + '"></span>' +
      esc(stem) + '<span class="cnt">' + fmt(counts[stem] || 0) +
      (priced ? "" : " · 시세없음") + '</span></div>';
  }
  box.innerHTML = html;
  box.querySelectorAll(".chip").forEach((el) => {
    el.onclick = () => { FILTER = el.dataset.f || null; renderChips(DATA); renderRanking(); };
  });
}

// ── 순위표 ──
function metricVal(r) { return METRIC === "deca" ? r.per_hour_deca : r.per_hour_count; }

const ROWSET = { all: "rows", paid: "rows_paid", free: "rows_free" };

function renderRanking() {
  const d = DATA;
  let rows = (d[ROWSET[MODE]] || d.rows).slice();
  if (FILTER) rows = rows.filter((r) => r.stem === FILTER);
  // 활성 지표 내림차순, 값 없는(시세 없음·표본 부족) 행은 아래로.
  rows.sort((a, b) => {
    const av = metricVal(a), bv = metricVal(b);
    if ((av == null) !== (bv == null)) return av == null ? 1 : -1;
    return (bv || 0) - (av || 0);
  });

  if (!rows.length) {
    $("ranking").innerHTML = '<div class="panel"><div class="empty">이 영혼석 기록이 없다</div></div>';
    return;
  }
  const maxV = Math.max(...rows.map((r) => metricVal(r) || 0), 1);
  const heroLabel = METRIC === "deca" ? "시간당 데카" : "시간당 개수";
  const otherLabel = METRIC === "deca" ? "시간당 개수" : "시간당 데카";

  // 시세 저장소가 아예 없으면(해연 도구 미실행) 데카 열이 전부 빈다.
  // 조용한 누락을 막으려 이유를 못박아 띄운다.
  const noPrices = !d.price_as_of;
  let h = "";
  if (noPrices) {
    h += '<div class="note" style="color:var(--warn-c);margin-top:0">' +
      '시세 없음 — 해연 원가 도구를 한 번 돌리면 데카가 채워진다. ' +
      '지금은 개수만 보인다.</div>';
  }

  h += '<div class="panel"><table><thead><tr>' +
    '<th>던전</th><th>영혼석</th><th>시세</th>' +
    '<th class="hero">' + heroLabel + '</th>' +
    '<th>' + otherLabel + '</th><th>판당</th><th>판수</th>' +
    '</tr></thead><tbody>';

  for (const r of rows) {
    const col = STONE[r.stem] || "var(--fg3)";
    const val = metricVal(r);
    const other = METRIC === "deca" ? r.per_hour_count : r.per_hour_deca;

    // 히어로 셀: 상대 길이 막대 + 값. 값 없으면 사유 표기.
    let hero;
    if (val != null) {
      const w = Math.max(2, (val / maxV) * 100);
      const fillCol = METRIC === "deca" ? "var(--deca-dim)"
        : "color-mix(in oklab, " + col + " 30%, transparent)";
      hero = '<td class="bar ' + (METRIC === "deca" ? "deca" : "") + '">' +
        '<div class="track" style="background:var(--inset)"></div>' +
        '<div class="fill" style="width:calc((100% - 28px) * ' + (w / 100) +
        ');background:' + fillCol + '"></div>' +
        '<span class="lab num">' + fmt(val, METRIC === "deca" ? 0 : 1) + '</span></td>';
    } else if (METRIC === "deca" && r.per_hour_count != null && r.price == null) {
      hero = '<td class="bar"><span class="sub2">시세 없음</span></td>';
    } else {
      hero = '<td class="bar"><span class="sub2">표본 ' + r.games + '판</span></td>';
    }

    h += '<tr class="rank-row" data-dungeon="' + esc(r.dungeon) + '" title="클릭 → 던전 상세">' +
      '<td class="dungeon"><div class="dcell">' +
        '<span class="sdot" style="background:' + col + '"></span>' +
        '<span class="dn">' + esc(r.dungeon) + '</span>' +
        (r.estimated ? '<span class="est" title="입장 방식을 전리품 칸 수로 추정">⁂</span>' : '') +
      '</div></td>' +
      '<td class="stone" style="color:' + col + '">' + esc(r.stem) + '</td>' +
      '<td class="price num">' + (r.price != null ? fmt(r.price) : "–") + '</td>' +
      hero +
      '<td class="dim num">' + (other != null ? fmt(other, METRIC === "deca" ? 1 : 0) : "–") + '</td>' +
      '<td class="dim num">' + fmt(r.count_per_game, 2) + '</td>' +
      '<td class="num">' + fmt(r.games) + '</td>' +
    '</tr>';
  }
  h += '</tbody></table></div>';
  h += '<div class="note">⁂ = 입장 방식을 전리품 칸 수로 추정한 던전. ' +
       '표본 ' + MIN + '판 미만·시세 없음은 히어로 값 대신 사유를 보인다.</div>';
  $("ranking").innerHTML = h;
}

// ── 활동량 차트 (인라인 SVG) — 막대=선택 지표, 선=시간당 데카 ──
const BAR_META = {
  deca_total: { label: "총 데카", from: "trend", fill: "rgba(232,184,75,.32)", fmtd: 0 },
  active_hours: { label: "가동 시간", from: "daily", fill: "rgba(233,216,180,.18)", fmtd: 1, suffix: "h" },
  games: { label: "판수", from: "daily", fill: "rgba(140,132,116,.5)", fmtd: 0 },
};
function renderChart() {
  const daily = DATA.daily || [];
  const trend = DATA.deca_trend || [];
  const box = $("chart");
  if (!daily.length) { box.innerHTML = '<div class="empty">기록 없음</div>'; return; }

  const meta = BAR_META[CHART_BAR] || BAR_META.deca_total;
  const barVal = (i) => meta.from === "trend"
    ? (trend[i] || {})[CHART_BAR] : daily[i][CHART_BAR];

  const W = Math.max(640, daily.length * 48), H = 224;
  const padL = 8, padR = 8, padT = 30, padB = 40;
  const iw = W - padL - padR, ih = H - padT - padB;
  const n = daily.length, colW = iw / n;
  const barMax = Math.max(...daily.map((_, i) => barVal(i) || 0), 0.01);
  const decaVals = trend.map((t) => t.deca_per_hour).filter((v) => v != null);
  const maxDeca = decaVals.length ? Math.max(...decaVals) : 0;

  const x = (i) => padL + colW * i + colW / 2;
  const barW = Math.min(26, colW * 0.56);
  let svg = '<svg viewBox="0 0 ' + W + ' ' + H + '" preserveAspectRatio="xMidYMid meet">';

  // 막대(선택 지표) + 값 라벨 + 판수(작게) + 날짜. 막대는 클릭 → 그날 필터.
  for (let i = 0; i < n; i++) {
    const v = barVal(i) || 0;
    const bh = (v / barMax) * ih;
    const bx = x(i) - barW / 2, by = padT + ih - bh;
    const sel = daily[i].date === DAY;
    // 열 전체 클릭 히트영역(투명)
    svg += '<rect class="day-hit" data-day="' + daily[i].date + '" x="' +
      (padL + colW * i).toFixed(1) + '" y="' + padT + '" width="' + colW.toFixed(1) +
      '" height="' + ih + '" fill="' + (sel ? "rgba(232,184,75,.08)" : "transparent") +
      '" style="cursor:pointer"/>';
    // 총 데카는 stacked(무료 아래 + 재화 위)로 재화 몫을 드러낸다. 선택된 날은
    // 통짜 강조색. 다른 지표(가동·판수)는 단일 막대.
    const tr = trend[i] || {};
    if (CHART_BAR === "deca_total" && !sel && (tr.paid_deca || tr.free_deca)) {
      const paid = tr.paid_deca || 0, free = tr.free_deca || 0, tot = paid + free || 1;
      const paidH = bh * (paid / tot), freeH = bh - paidH;
      svg += '<rect data-day="' + daily[i].date + '" x="' + bx.toFixed(1) + '" y="' +
        (padT + ih - freeH).toFixed(1) + '" width="' + barW + '" height="' +
        Math.max(0.5, freeH).toFixed(1) + '" rx="2" fill="rgba(233,216,180,.28)" style="cursor:pointer"/>';
      if (paid > 0)
        svg += '<rect data-day="' + daily[i].date + '" x="' + bx.toFixed(1) + '" y="' +
          by.toFixed(1) + '" width="' + barW + '" height="' + Math.max(1, paidH).toFixed(1) +
          '" rx="2" fill="rgba(232,184,75,.85)" style="cursor:pointer"/>';
    } else {
      svg += '<rect data-day="' + daily[i].date + '" x="' + bx.toFixed(1) + '" y="' +
        by.toFixed(1) + '" width="' + barW + '" height="' + Math.max(1, bh).toFixed(1) +
        '" rx="3" fill="' + (sel ? "var(--deca)" : meta.fill) +
        '" style="cursor:pointer"/>';
    }
    // 막대 값(선택 지표)
    if (barVal(i) != null) {
      svg += '<text x="' + x(i).toFixed(1) + '" y="' + (by - 15).toFixed(1) +
        '" text-anchor="middle" font-size="10" fill="#c6bba6" ' +
        'font-family="ui-monospace,monospace">' + fmt(v, meta.fmtd) + (meta.suffix || "") + '</text>';
    }
    // 판수(맥락, 더 작게 회색)
    svg += '<text x="' + x(i).toFixed(1) + '" y="' + (by - 4).toFixed(1) +
      '" text-anchor="middle" font-size="9" fill="#6f6858" ' +
      'font-family="ui-monospace,monospace">' + daily[i].games + '판</text>';
    svg += '<text x="' + x(i).toFixed(1) + '" y="' + (H - 8) +
      '" text-anchor="middle" font-size="11" fill="#8d8474" ' +
      'font-family="ui-monospace,monospace">' + daily[i].date + '</text>';
  }

  // 시간당 데카 추세선 — 자체 스케일, 금색. null 구간은 끊는다.
  if (maxDeca > 0) {
    const y = (v) => padT + ih - (v / maxDeca) * ih;
    let segs = [], cur = [];
    for (let i = 0; i < n; i++) {
      const v = (trend[i] || {}).deca_per_hour;
      if (v == null) { if (cur.length) { segs.push(cur); cur = []; } }
      else cur.push([x(i), y(v)]);
    }
    if (cur.length) segs.push(cur);
    for (const seg of segs) {
      const pts = seg.map((p) => p[0].toFixed(1) + "," + p[1].toFixed(1)).join(" ");
      svg += '<polyline points="' + pts + '" fill="none" stroke="#e8b84b" ' +
        'stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>';
      for (const p of seg)
        svg += '<circle cx="' + p[0].toFixed(1) + '" cy="' + p[1].toFixed(1) + '" r="2.5" fill="#e8b84b"/>';
    }
  }
  svg += '</svg>';

  const barLegend = CHART_BAR === "deca_total"
    ? '<span class="k"><span class="swatch" style="background:rgba(232,184,75,.85)"></span>재화 판 데카</span>' +
      '<span class="k"><span class="swatch" style="background:rgba(233,216,180,.5)"></span>무료 판 데카</span>'
    : '<span class="k"><span class="swatch" style="background:' + meta.fill.replace(/[\d.]+\)$/, "1)") + '"></span>' + meta.label + '(막대)</span>';
  const legend = '<div class="legend">' +
    barLegend +
    (maxDeca > 0
      ? '<span class="k"><span class="swatch" style="background:#e8b84b"></span>시간당 데카 · 현재 시세 기준(선)</span>'
      : '<span class="k muted">데카는 시세가 있어야 나온다</span>') +
    '<span class="k muted">막대 클릭 → 그날 필터</span>' +
    '</div>';
  box.innerHTML = svg + legend;
}

function renderToggle() {
  $("toggle").querySelectorAll("button").forEach((b) =>
    b.classList.toggle("on", b.dataset.metric === METRIC));
  $("mode").querySelectorAll("button").forEach((b) =>
    b.classList.toggle("on", b.dataset.mode === MODE));

  // 재화/무료는 전리품으로 가른다. 재화 판이 얇으면 표본 부족을 알린다.
  const note = $("mode-note");
  const pg = DATA ? (DATA.paid_games || 0) : 0;
  const total = DATA ? (DATA.period.total_games || 0) : 0;
  if (MODE === "paid") {
    note.innerHTML = "재화(은동전/공물) 판 = 재화 전용 전리품(파편·조각난 보석·미스틱 다이스 등)이 나온 판. " +
      "총 <b class='num'>" + fmt(pg) + "</b>판(" + fmt(total ? pg / total * 100 : 0, 1) +
      "%)뿐이라 던전 대부분 표본 부족 — 데카 대신 판수를 보인다.";
    note.style.display = "block";
  } else if (MODE === "free") {
    note.textContent = "무료 판 = base 전리품(영혼석·증표·화폐)만 나온 판. 대부분의 판이 여기 든다.";
    note.style.display = "block";
  } else {
    note.style.display = "none";
  }
}

// ── 진단 패널(#1): 기타·종류 불명·기타 던전 원문을 다 펼쳐 교정하러 간다 ──
function diagList(obj, emptyMsg) {
  const rows = Object.entries(obj || {});
  if (!rows.length) return '<div class="empty2">' + emptyMsg + '</div>';
  return '<div class="list">' + rows.map(([n, c]) =>
    '<div><span class="nm" title="' + esc(n) + '">' + esc(n) +
    '</span><span class="c num">×' + fmt(c) + '</span></div>').join("") + '</div>';
}
function renderDiag() {
  const d = DATA;
  $("diag").innerHTML =
    '<div class="dhead"><span>원문 진단 — 조용히 버린 건 없다</span>' +
    '<span class="path">교정: <code>' + esc(d.corrections_path) +
    '</code> 편집 후 새로고침</span></div>' +
    '<div class="cols">' +
      '<div class="col"><h4>기타(미집계) · 영혼석 아닌 아이템</h4>' +
        diagList(d.other_items, "없음") + '</div>' +
      '<div class="col"><h4>종류 불명 · 어간 못 가른 영혼석</h4>' +
        diagList(d.unknown_items, "없음") + '</div>' +
      '<div class="col"><h4>기타 던전 · area 못 가린 raw 던전명</h4>' +
        diagList(d.misc_dungeons, "없음") + '</div>' +
    '</div>';
}

// ── 전체 데이터 브라우저 ──
let RECORDS = [];
function recMatch(r, q) {
  if (!q) return true;
  const hay = ((r.canon || "") + " " + (r.dungeon || "") + " " + r.mode + " " +
    r.items.map((i) => i.raw + " " + i.tag).join(" ")).toLowerCase();
  return q.split(/\s+/).every((w) => hay.includes(w));
}
function recDay(iso) {  // 그 판의 KST 날짜 "MM/DD"
  return new Date(iso).toLocaleDateString("en-CA", { timeZone: "Asia/Seoul" })
    .slice(5).replace("-", "/");
}
function renderRecords() {
  const q = ($("rec-search").value || "").trim().toLowerCase();
  const all = RECORDS.filter(
    (r) => recMatch(r, q) && (!DAY || recDay(r.at) === DAY));
  const LIMIT = 300, shown = all.slice(0, LIMIT);
  $("rec-count").textContent = fmt(all.length) + "판" +
    (all.length > LIMIT ? " 중 " + LIMIT + " 표시" : "") + (q ? " · 검색됨" : "");
  if (!shown.length) { $("records").innerHTML = '<div class="empty">해당 판 없음</div>'; return; }
  let h = '<table><thead><tr><th>시각(KST)</th><th>던전</th><th>입장</th><th>전리품</th>' +
    '</tr></thead><tbody>';
  for (const r of shown) {
    const canon = r.canon || "—";
    const rawDiff = r.dungeon && r.dungeon !== canon
      ? '<div class="raw">' + esc(r.dungeon) + '</div>' : '';
    const items = r.items.map((i) => {
      const cls = i.tag.indexOf("영혼석") === 0 ? "soul" : i.tag;
      return '<span class="it ' + cls + '" title="' + esc(i.tag) + '">' + esc(i.raw) + '</span>';
    }).join("") || '<span class="muted">전리품 없음</span>';
    h += '<tr class="rec-row" data-idx="' + r.idx + '" title="클릭 → 이 판 수정">' +
      '<td class="at num">' + shortTime(r.at) + '</td>' +
      '<td class="dg">' + esc(canon) + rawDiff + '</td>' +
      '<td><span class="mtag ' + r.mode + '">' + r.mode + '</span></td>' +
      '<td class="items-cell">' + items + '</td></tr>';
  }
  $("records").innerHTML = h + '</tbody></table>';
}
async function loadRecords() {
  $("records").innerHTML = '<div class="empty">불러오는 중…</div>';
  const res = await fetch("/api/records");
  RECORDS = (await res.json()).records || [];
  renderRecords();
}

// ── 교정 편집기 ──
async function loadCorrections() {
  const res = await fetch("/api/corrections");
  $("corr-text").value = (await res.json()).text || "";
}
async function saveCorrections() {
  const st = $("corr-status");
  st.textContent = "저장 중…"; st.className = "ed-status";
  try {
    const res = await fetch("/api/corrections", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: $("corr-text").value }),
    });
    const d = await res.json();
    if (!d.ok) { st.textContent = "✕ " + d.error; st.className = "ed-status err"; return; }
    st.textContent = "저장됨 · 전체 재적용 중…"; st.className = "ed-status ok";
    await load(); await loadRecords();
    st.textContent = "✓ 저장·재적용 완료";
  } catch (e) { st.textContent = "✕ " + e; st.className = "ed-status err"; }
}

// ── 탭 ──
function switchTab(name) {
  $("tabs").querySelectorAll("button").forEach((b) =>
    b.classList.toggle("on", b.dataset.tab === name));
  $("pane-rank").hidden = name !== "rank";
  $("pane-records").hidden = name !== "records";
  $("pane-edit").hidden = name !== "edit";
}

// ── 던전 상세 (순위 행 클릭) ──
function tile(label, value, deca) {
  return '<div class="dt-tile"><div class="tl">' + label + '</div>' +
    '<div class="tv num' + (deca ? ' deca' : '') + '">' + value + '</div></div>';
}
function dropChart(daily, col) {
  // 날짜마다 무료(연한)·재화(진한 금색) 드랍률 막대를 나란히. 그날 그 모드로
  // 돈 판이 없으면 그 막대는 생략. 패치+재화 효과를 같은 날에서 바로 비교한다.
  const maxV = Math.max(0.01, ...daily.flatMap((r) =>
    [r.per_game, r.free_per_game || 0, r.paid_per_game || 0]));
  const W = Math.max(560, daily.length * 48), H = 162;
  const padL = 8, padR = 8, padT = 22, padB = 34;
  const iw = W - padL - padR, ih = H - padT - padB, n = daily.length, colW = iw / n;
  const x = (i) => padL + colW * i + colW / 2, bw = Math.min(11, colW * 0.3);
  let svg = '<svg viewBox="0 0 ' + W + ' ' + H + '" preserveAspectRatio="xMidYMid meet">';
  const bar = (v, bx, fill, tcol) => {
    const bh = (v / maxV) * ih, by = padT + ih - bh;
    let s = '<rect x="' + bx.toFixed(1) + '" y="' + by.toFixed(1) + '" width="' + bw.toFixed(1) +
      '" height="' + Math.max(1, bh).toFixed(1) + '" rx="2" fill="' + fill + '"/>';
    s += '<text x="' + (bx + bw / 2).toFixed(1) + '" y="' + (by - 4).toFixed(1) +
      '" text-anchor="middle" font-size="8" fill="' + tcol + '" font-family="ui-monospace,monospace">' +
      v.toFixed(2) + '</text>';
    return s;
  };
  for (let i = 0; i < n; i++) {
    const r = daily[i], cx = x(i);
    if (r.free_games) svg += bar(r.free_per_game || 0, cx - bw - 1, "rgba(233,216,180,.5)", "#8d8474");
    if (r.paid_games) svg += bar(r.paid_per_game || 0, cx + 1, "rgba(232,184,75,.85)", "#c99a2e");
    svg += '<text x="' + cx.toFixed(1) + '" y="' + (H - 18) +
      '" text-anchor="middle" font-size="10" fill="#8d8474" font-family="ui-monospace,monospace">' +
      r.date + '</text>';
    // 판수(재화·무료) 아주 작게
    svg += '<text x="' + cx.toFixed(1) + '" y="' + (H - 7) +
      '" text-anchor="middle" font-size="8" fill="#6f6858" font-family="ui-monospace,monospace">' +
      (r.paid_games ? "재" + r.paid_games + " " : "") + "무" + (r.free_games || 0) + '</text>';
  }
  return svg + '</svg>';
}
function sideBox(title, s, price) {
  const phd = s.per_hour_deca != null ? fmt(s.per_hour_deca) : "표본 " + s.games + "판";
  return '<div class="dt-mini"><h5>' + title + ' · ' + fmt(s.games) + '판</h5>' +
    '<div class="row"><span class="lb">판당 개수</span><span class="num">' + fmt(s.per_game, 3) + '</span></div>' +
    '<div class="row"><span class="lb">시간당 개수</span><span class="num">' +
      (s.per_hour_count != null ? fmt(s.per_hour_count, 1) : "–") + '</span></div>' +
    '<div class="row"><span class="lb">시간당 데카</span><span class="num" style="color:var(--deca)">' +
      phd + '</span></div></div>';
}
function hm(iso) {
  return new Date(iso).toLocaleString("ko-KR",
    { timeZone: "Asia/Seoul", hour: "2-digit", minute: "2-digit" });
}
function sessionRows(sessions) {
  const rows = (sessions || []).slice(0, 40);
  if (!rows.length) return '<div class="empty2">없음</div>';
  return rows.map((s) => {
    const mins = Math.round((new Date(s.end) - new Date(s.start)) / 60000);
    const split = s.paid ? ' <span style="color:var(--deca)">재' + s.paid + '</span>·무' + (s.free || 0) : "";
    return '<div class="row"><span class="lb">' + shortTime(s.start) + " ~ " + hm(s.end) +
      '</span><span class="num">' + fmt(s.games) + "판" + split + " · " + fmt(mins) + '분</span></div>';
  }).join("");
}
async function openDetail(dungeon) {
  const panel = $("detail-panel");
  panel.innerHTML = '<div class="empty">불러오는 중…</div>';
  $("detail-overlay").classList.add("open");
  const res = await fetch("/api/dungeon?name=" + encodeURIComponent(dungeon));
  if (!res.ok) { panel.innerHTML = '<div class="empty">기록 없음</div>'; return; }
  const d = await res.json();
  const col = STONE[d.stem] || "var(--fg3)";
  const dropRate = d.drop_rate != null ? fmt(d.drop_rate, 1) + "판당 1개" : "–";
  const lootRows = (obj) => Object.entries(obj || {}).slice(0, 20).map(([n, c]) =>
    '<div class="row"><span class="lb">' + esc(n) + '</span><span class="num">×' + fmt(c) + '</span></div>').join("")
    || '<div class="empty2">없음</div>';
  const otherPaidRows = lootRows(d.other_paid);
  const otherFreeRows = lootRows(d.other_free);
  // 시간대: 시별 재화/무료 판수 병기.
  const hp = d.hours_paid || {}, hf = d.hours_free || {};
  const hourBars = Object.entries(d.hours || {}).map(([hh, c]) => {
    const p = hp[hh] || 0, f = hf[hh] || 0;
    const split = p ? ' <span style="color:var(--deca)">재' + p + '</span>·무' + f : "";
    return '<div class="row"><span class="lb">' + hh + '시</span><span class="num">' + fmt(c) + '판' + split + '</span></div>';
  }).join("") || '<div class="empty2">없음</div>';

  panel.innerHTML =
    '<div class="dt-head"><div><div class="dt-title">' +
      '<span class="sdot" style="display:inline-block;width:11px;height:11px;border-radius:50%;background:' + col + ';margin-right:8px"></span>' +
      esc(d.dungeon) + '</div>' +
      '<div class="dt-sub">영혼석 ' + esc(d.stem || "—") + (d.deep ? " · 심층(더블 없음)" : " · 비심층") +
        ' · ' + shortTime(d.first) + " ~ " + shortTime(d.last) + '</div></div>' +
      '<button class="dt-close" id="dt-close">닫기 ✕</button></div>' +
    '<div class="dt-tiles">' +
      tile("판수", fmt(d.games)) +
      tile("판당 개수", fmt(d.per_game, 3)) +
      tile("시간당 데카", d.per_hour_deca != null ? fmt(d.per_hour_deca) : "표본부족", true) +
      tile("총 데카 누적", d.total_deca != null ? fmt(d.total_deca) : "–", true) +
      tile("드랍률", dropRate) +
      tile("판당 소요", d.games_per_hour ? fmt(3600 / d.games_per_hour, 0) + "초" : "–") +
    '</div>' +
    '<div class="dt-sec">돌린 구간 — 언제 돌렸나 (총 ' + shortTime(d.first) + ' ~ ' + shortTime(d.last) + ')</div>' +
    '<div class="dt-mini"><div class="dt-list">' + sessionRows(d.sessions) + '</div></div>' +
    '<div class="dt-sec">날짜별 드랍률 추이 (개/판) — 패치로 확률이 바뀌었는지 ' +
      '<span style="color:var(--deca)">■재화</span> <span style="color:#c6bba6">■무료</span></div>' +
    '<div class="dt-chart">' + dropChart(d.daily, col) + '</div>' +
    '<div class="dt-sec">재화 / 무료</div>' +
    '<div class="dt-two">' + sideBox("재화", d.paid, d.price) + sideBox("무료", d.free, d.price) + '</div>' +
    '<div class="dt-sec">전리품 구성 — 재화 판 vs 무료 판 (뭐가 더 나오나)</div>' +
    '<div class="dt-two"><div class="dt-mini"><h5 style="color:var(--deca)">재화 판 전리품</h5><div class="dt-list">' + otherPaidRows + '</div></div>' +
      '<div class="dt-mini"><h5>무료 판 전리품</h5><div class="dt-list">' + otherFreeRows + '</div></div></div>' +
    '<div class="dt-sec">시간대(KST) 분포</div>' +
    '<div class="dt-mini"><div class="dt-list">' + hourBars + '</div></div>' +
    '<div class="dt-sec"><a href="#" id="dt-records" style="color:var(--deca)">이 던전 개별 판 목록 보기 →</a></div>';

  $("dt-close").onclick = () => $("detail-overlay").classList.remove("open");
  $("dt-records").onclick = (e) => {
    e.preventDefault();
    $("detail-overlay").classList.remove("open");
    switchTab("records");
    $("rec-search").value = d.dungeon; renderRecords();
  };
}

// ── 개별 판 수정 (전체 데이터 행 클릭) — 모든 필드 편집 가능 ──
function openEdit(idx) {
  const r = RECORDS.find((x) => x.idx === idx);
  if (!r) return;
  const rec = r.record || {};
  const rest = Object.assign({}, rec);           // 나머지 필드(고급 JSON)
  delete rest.dungeon; delete rest.items; delete rest.mode;
  const modeVal = r.mode_forced ? r.mode : "auto";
  const items = (rec.items || []).join("\n");
  const seg = (v, lb) => '<button data-m="' + v + '"' +
    (modeVal === v ? ' class="on"' : '') + '>' + lb + '</button>';
  $("edit-panel").innerHTML =
    '<div class="dt-head"><div><div class="dt-title">이 판 수정</div>' +
      '<div class="dt-sub">' + shortTime(r.at) + " · 판 #" + idx + '</div></div>' +
      '<button class="dt-close" id="ed-close">닫기 ✕</button></div>' +
    '<div class="ed-field"><label>던전명 (raw)</label>' +
      '<input id="ed-dungeon" value="' + esc(rec.dungeon || "") + '"/>' +
      '<div class="hint">정규화: ' + esc(r.canon || "—") + '</div></div>' +
    '<div class="ed-field"><label>재화 / 무료</label>' +
      '<div class="toggle" id="ed-mode" style="width:fit-content">' +
        seg("auto", "자동(표식)") + seg("재화", "재화") + seg("무료", "무료") + '</div>' +
      '<div class="hint">자동 = 전리품 표식으로 판별. 재화/무료 = 이 판을 못박는다(mode 오버라이드).</div></div>' +
    '<div class="ed-field"><label>전리품 (한 줄에 하나)</label>' +
      '<textarea id="ed-items">' + esc(items) + '</textarea></div>' +
    '<div class="ed-field"><label>나머지 필드 (전체 JSON — 다 편집 가능)</label>' +
      '<textarea id="ed-rest">' + esc(JSON.stringify(rest, null, 2)) + '</textarea>' +
      '<div class="hint">at·entry·quantities·combatSeconds 등. JSON 형식 유지.</div></div>' +
    '<div class="editor-bar"><button class="save" id="ed-save">저장(로그 수정)</button>' +
      '<span id="ed-status" class="ed-status"></span></div>' +
    '<div class="note" style="margin-top:10px">로그 원본을 직접 고친다. <code>.jsonl.bak</code> 백업됨. 봇이 도는 중이면 멈추고 하는 게 안전하다.</div>';
  $("edit-overlay").classList.add("open");
  $("ed-close").onclick = () => $("edit-overlay").classList.remove("open");
  $("ed-mode").onclick = (e) => {
    const b = e.target.closest("button"); if (!b) return;
    $("ed-mode").querySelectorAll("button").forEach((x) =>
      x.classList.toggle("on", x === b));
  };
  $("ed-save").onclick = () => saveRecord(idx);
}
async function saveRecord(idx) {
  const st = $("ed-status");
  st.textContent = "저장 중…"; st.className = "ed-status";
  let base;
  try {
    base = JSON.parse($("ed-rest").value || "{}");
  } catch (e) {
    st.textContent = "✕ 나머지 JSON 오류: " + e; st.className = "ed-status err"; return;
  }
  base.dungeon = $("ed-dungeon").value;
  base.items = $("ed-items").value.split("\n").map((s) => s.trim()).filter(Boolean);
  const mv = $("ed-mode").querySelector("button.on").dataset.m;
  if (mv === "auto") delete base.mode; else base.mode = mv;
  try {
    const res = await fetch("/api/record", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ idx, record: base }),
    });
    const d = await res.json();
    if (!d.ok) { st.textContent = "✕ " + d.error; st.className = "ed-status err"; return; }
    st.textContent = "✓ 저장됨 · 재적용 중…"; st.className = "ed-status ok";
    await load(); await loadRecords();
    $("edit-overlay").classList.remove("open");
  } catch (e) { st.textContent = "✕ " + e; st.className = "ed-status err"; }
}

async function load() {
  const res = await fetch("/api/data" + (DAY ? "?day=" + encodeURIComponent(DAY) : ""));
  DATA = await res.json();
  MIN = DATA.min_samples || 20;
  renderHeader(DATA);
  renderDayBar();
  renderDiag();
  renderChips(DATA);
  renderToggle();
  renderRanking();
  renderChart();
}

// 날짜 필터 안내 + 해제
function renderDayBar() {
  const bar = $("day-bar");
  if (DAY) {
    bar.innerHTML = "<b class='num'>" + DAY + "</b> 하루만 보는 중 · " +
      "<b class='num'>" + fmt(DATA.day_games || 0) + "</b>판 " +
      "<button id='day-clear'>전체 기간 ✕</button>";
    bar.style.display = "flex";
    $("day-clear").onclick = () => { DAY = null; load(); loadRecords(); };
  } else {
    bar.style.display = "none";
  }
}

$("toggle").addEventListener("click", (e) => {
  const b = e.target.closest("button"); if (!b) return;
  METRIC = b.dataset.metric; renderToggle(); renderRanking();
});
$("mode").addEventListener("click", (e) => {
  const b = e.target.closest("button"); if (!b) return;
  MODE = b.dataset.mode; renderChips(DATA); renderToggle(); renderRanking();
});
$("chart-bar").addEventListener("click", (e) => {
  const b = e.target.closest("button"); if (!b) return;
  CHART_BAR = b.dataset.cb;
  $("chart-bar").querySelectorAll("button").forEach((x) => x.classList.toggle("on", x === b));
  renderChart();
});
// 차트 막대 클릭 → 그날 필터(같은 날 다시 누르면 해제)
$("chart").addEventListener("click", (e) => {
  const d = e.target.getAttribute && e.target.getAttribute("data-day");
  if (!d) return;
  DAY = DAY === d ? null : d;
  load(); loadRecords();
});
const toggleDiag = () => $("diag").classList.toggle("open");
$("stat-other").addEventListener("click", toggleDiag);
$("stat-unknown").addEventListener("click", toggleDiag);
$("rec-search").addEventListener("input", renderRecords);
$("corr-save").addEventListener("click", saveCorrections);
$("tabs").addEventListener("click", (e) => {
  const b = e.target.closest("button"); if (b) switchTab(b.dataset.tab);
});
$("ranking").addEventListener("click", (e) => {
  const tr = e.target.closest(".rank-row"); if (tr) openDetail(tr.dataset.dungeon);
});
$("records").addEventListener("click", (e) => {
  const tr = e.target.closest(".rec-row"); if (tr) openEdit(+tr.dataset.idx);
});
// 오버레이 바깥 클릭 → 닫기
$("detail-overlay").addEventListener("click", (e) => {
  if (e.target.id === "detail-overlay") e.currentTarget.classList.remove("open");
});
$("edit-overlay").addEventListener("click", (e) => {
  if (e.target.id === "edit-overlay") e.currentTarget.classList.remove("open");
});
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") {
    $("detail-overlay").classList.remove("open");
    $("edit-overlay").classList.remove("open");
  }
});
$("refresh").addEventListener("click", () => { load(); loadRecords(); });
load();
loadRecords();
loadCorrections();
</script>
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):
    directory = "."

    def _send(self, code, body, content_type):
        data = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _json(self, code, obj):
        self._send(
            code, json.dumps(obj, ensure_ascii=False), "application/json; charset=utf-8"
        )

    def do_GET(self):
        if self.path.startswith("/api/data"):
            q = urllib.parse.urlparse(self.path).query
            day = urllib.parse.parse_qs(q).get("day", [None])[0]
            self._json(200, build_payload(self.directory, day=day))
        elif self.path.startswith("/api/records"):
            self._json(200, {"records": build_records(self.directory)})
        elif self.path.startswith("/api/dungeon"):
            q = urllib.parse.urlparse(self.path).query
            name = urllib.parse.parse_qs(q).get("name", [""])[0]
            detail = build_dungeon(self.directory, name)
            if detail is None:
                self._json(404, {"error": "던전 기록 없음"})
            else:
                self._json(200, detail)
        elif self.path.startswith("/api/corrections"):
            path = analyze.CORRECTIONS_PATH
            text = path.read_text(encoding="utf-8") if path.exists() else "{}"
            self._json(200, {"text": text, "path": str(path)})
        elif self.path == "/" or self.path.startswith("/index"):
            self._send(200, PAGE, "text/html; charset=utf-8")
        else:
            self._send(404, "not found", "text/plain; charset=utf-8")

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length).decode("utf-8")
        if self.path.startswith("/api/corrections"):
            try:
                text = json.loads(raw)["text"]
            except (ValueError, KeyError, TypeError):
                self._json(400, {"ok": False, "error": "요청 형식 오류"})
                return
            try:
                save_corrections_text(text)  # 깨진 JSON이면 ValueError
            except ValueError as exc:
                self._json(400, {"ok": False, "error": f"JSON 오류: {exc}"})
                return
            except OSError as exc:
                self._json(500, {"ok": False, "error": f"저장 실패: {exc}"})
                return
            self._json(200, {"ok": True})
        elif self.path.startswith("/api/record"):
            try:
                body = json.loads(raw)
                idx = int(body["idx"])
                record = body["record"]
            except (ValueError, KeyError, TypeError):
                self._json(400, {"ok": False, "error": "요청 형식 오류"})
                return
            try:
                edit_record(self.directory, idx, record)
            except (IndexError, ValueError) as exc:
                self._json(400, {"ok": False, "error": str(exc)})
                return
            except OSError as exc:
                self._json(500, {"ok": False, "error": f"저장 실패: {exc}"})
                return
            self._json(200, {"ok": True})
        else:
            self._send(404, "not found", "text/plain; charset=utf-8")

    def log_message(self, *args):
        pass  # 조용히


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dir", default=str(analyze.LOG_DIR), help="로그 디렉터리")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()

    Handler.directory = args.dir
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    url = f"http://127.0.0.1:{args.port}/"
    print(f"영혼석 대시보드: {url}")
    print(f"로그: {pathlib.Path(args.dir).expanduser() / 'cycle-log.jsonl'}")
    print("Ctrl-C로 종료")
    if not args.no_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n종료")
        server.shutdown()


if __name__ == "__main__":
    main()
