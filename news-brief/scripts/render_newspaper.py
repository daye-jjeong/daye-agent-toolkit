#!/usr/bin/env python3
"""Render news briefing JSON into newspaper-style HTML.

Input JSON schema:
{
  "date": "2026-02-12",
  "sections": [
    {
      "title": "AI & Tech Trends",
      "items": [
        {
          "headline": "헤드라인 제목",
          "summary": "요약 텍스트",
          "source": "TechCrunch",
          "url": "https://...",
          "tag": "Models",
          "why": "왜 중요한가 (optional)"
        }
      ],
      "insight": "적용 아이디어 (optional)"
    }
  ],
  "highlight": "오늘의 핵심 한줄 (optional)"
}

Ronik items may use opportunity/risk/action instead of summary/why.

Usage:
  echo '...' | python3 render_newspaper.py
  python3 render_newspaper.py --input data.json
  python3 render_newspaper.py --input data.json --output /tmp/daily.html

Output defaults to stdout. Use --output to write a file.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from html import escape

WEEKDAYS = ["월", "화", "수", "목", "금", "토", "일"]

CSS = """\
@import url('https://fonts.googleapis.com/css2?family=Noto+Serif+KR:wght@400;700&family=Noto+Sans+KR:wght@300;400;500;700&display=swap');

*{margin:0;padding:0;box-sizing:border-box}

body{
  background:#f4f1ec;
  color:#1a1a1a;
  font-family:'Noto Sans KR',-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
  font-size:15px;
  line-height:1.6;
  padding:1rem;
}

.newspaper{
  max-width:720px;
  margin:0 auto;
  background:#fff;
  box-shadow:0 1px 12px rgba(0,0,0,.06);
}

/* ── Masthead ── */
.masthead{
  text-align:center;
  padding:2.5rem 2rem 1.5rem;
}
.masthead .rule-top{height:1px;background:#1a1a1a;margin-bottom:.6rem}
.masthead .rule-top2{height:3px;background:#1a1a1a;margin-bottom:1.2rem}
.masthead h1{
  font-family:'Noto Serif KR',Georgia,serif;
  font-size:2.8rem;font-weight:700;
  letter-spacing:.2em;line-height:1.2;
}
.masthead .subtitle{
  font-size:.7rem;letter-spacing:.5em;
  color:#888;margin-top:.3rem;text-transform:uppercase;
}
.masthead .dateline{
  font-size:.85rem;color:#666;
  margin-top:.8rem;padding-top:.8rem;
  border-top:1px solid #ddd;
}
.masthead .rule-bottom{height:3px;background:#1a1a1a;margin-top:1.2rem}

/* ── Section ── */
.section{padding:1.8rem 2rem;border-bottom:1px solid #e8e5e0}
.section-title{
  font-size:.72rem;font-weight:700;
  text-transform:uppercase;letter-spacing:.25em;
  color:#8b0000;
  border-bottom:2px solid #8b0000;
  display:inline-block;padding-bottom:.25rem;
  margin-bottom:1.2rem;
}

/* ── Item ── */
.item{margin-bottom:1.4rem}
.item:last-child{margin-bottom:0}
.item-headline{
  font-family:'Noto Serif KR',Georgia,serif;
  font-size:1.08rem;font-weight:700;line-height:1.45;
  margin-bottom:.2rem;
}
.item-headline a{
  color:#1a1a1a;text-decoration:none;
  border-bottom:1px solid transparent;
  transition:border-color .2s;
}
.item-headline a:hover{border-bottom-color:#8b0000}

.item-meta{
  font-size:.75rem;color:#999;
  margin-bottom:.3rem;
  display:flex;gap:.5rem;align-items:center;
}
.item-meta .source{color:#777}
.item-meta .tag{
  background:#f0ede8;color:#666;
  padding:.1rem .45rem;border-radius:3px;font-size:.7rem;
}
.item-meta .published{color:#aaa;font-size:.7rem}

.item-summary{font-size:.92rem;color:#333;line-height:1.55}
.item-why{
  font-size:.84rem;color:#555;font-style:italic;
  margin-top:.25rem;padding-left:.5rem;
  border-left:2px solid #e8e5e0;
}

/* ── Ronik analysis ── */
.ronik-analysis{font-size:.88rem;margin-top:.3rem;padding-left:.5rem}
.ronik-analysis p{margin:.15rem 0;line-height:1.4}
.ronik-analysis .opp{color:#2d6a4f}
.ronik-analysis .risk{color:#9d4b00}
.ronik-analysis .action{color:#1a5276}

/* ── Section insight ── */
.section-insight{
  margin-top:1.2rem;padding:.8rem 1rem;
  background:#f8f7f4;border-radius:4px;
  font-size:.88rem;color:#444;
}

/* ── Highlight ── */
.highlight{
  padding:1.5rem 2rem;
  background:#fffcf0;border-left:4px solid #c8a84e;
}
.highlight-label{
  font-weight:700;font-size:.82rem;
  color:#8b6914;letter-spacing:.1em;margin-bottom:.3rem;
}
.highlight-text{
  font-family:'Noto Serif KR',Georgia,serif;
  font-size:1.05rem;line-height:1.5;color:#333;
}

/* ── Weather ── */
.weather-box{
  margin:0 2rem;padding:1.2rem 1.5rem;
  background:linear-gradient(135deg,#f8f9fb 0%,#eef1f5 100%);
  border:1px solid #e0ddd8;border-radius:6px;
}
.weather-row{
  display:flex;justify-content:space-between;
  align-items:center;flex-wrap:wrap;gap:.8rem;
}
.weather-main{display:flex;align-items:baseline;gap:.6rem}
.weather-temp{
  font-family:'Noto Serif KR',Georgia,serif;
  font-size:2.2rem;font-weight:700;line-height:1;
}
.weather-feels{font-size:.8rem;color:#888}
.weather-cond{font-size:.92rem;color:#555}
.weather-detail{font-size:.78rem;color:#888;line-height:1.5}
.weather-outfit{
  margin-top:.8rem;padding-top:.8rem;
  border-top:1px solid #e0ddd8;
  font-size:.88rem;color:#444;
}
.weather-outfit strong{color:#1a5276}
.weather-label{
  font-size:.68rem;font-weight:700;
  text-transform:uppercase;letter-spacing:.2em;
  color:#888;margin-bottom:.6rem;
}

/* ── Footer ── */
.colophon{
  text-align:center;padding:1.2rem;
  font-size:.72rem;color:#bbb;
  border-top:1px solid #e8e5e0;
}

@media print{
  body{background:#fff;padding:0}
  .newspaper{box-shadow:none;max-width:100%}
}
@media(max-width:480px){
  .masthead h1{font-size:2rem;letter-spacing:.1em}
  .section{padding:1.2rem 1rem}
  .highlight{padding:1rem}
}
"""


def korean_date(date_str: str) -> str:
    d = datetime.strptime(date_str, "%Y-%m-%d")
    return f"{d.year}년 {d.month}월 {d.day}일 {WEEKDAYS[d.weekday()]}요일"


def render_weather(weather: dict) -> str:
    """Render weather box HTML from fetch_weather.py output."""
    loc = escape(weather.get("location", ""))
    temp = weather.get("current_temp", "?")
    feels = weather.get("feels_like", "?")
    high = weather.get("high", "?")
    low = weather.get("low", "?")
    cond = escape(weather.get("condition", ""))
    humidity = weather.get("humidity", "?")
    wind = escape(weather.get("wind", ""))
    outfit = weather.get("outfit", {})

    outfit_summary = escape(outfit.get("summary", ""))

    return f"""\
    <div class="weather-box">
      <p class="weather-label">{loc} 날씨</p>
      <div class="weather-row">
        <div>
          <div class="weather-main">
            <span class="weather-temp">{temp}°</span>
            <span class="weather-feels">체감 {feels}°</span>
          </div>
          <div class="weather-cond">{cond} · 최고 {high}° / 최저 {low}°</div>
        </div>
        <div class="weather-detail">
          습도 {humidity}%<br>바람 {wind}
        </div>
      </div>
      <div class="weather-outfit">
        👔 <strong>오늘의 옷차림</strong> — {outfit_summary}
      </div>
    </div>"""


def render_item(item: dict) -> str:
    h = escape(item.get("headline", ""))
    url = escape(item.get("url", "#"))
    source = escape(item.get("source", ""))
    tag = escape(item.get("tag", ""))
    published = escape(item.get("published", ""))

    parts: list[str] = ['<article class="item">']
    parts.append(
        f'  <h3 class="item-headline">'
        f'<a href="{url}" target="_blank" rel="noopener">{h}</a></h3>'
    )

    meta: list[str] = []
    if source:
        meta.append(f'<span class="source">{source}</span>')
    if tag:
        meta.append(f'<span class="tag">{tag}</span>')
    if published:
        meta.append(f'<span class="published">{published}</span>')
    if meta:
        parts.append(f'  <div class="item-meta">{" ".join(meta)}</div>')

    # Ronik format: opportunity / risk / action
    if "opportunity" in item:
        parts.append('  <div class="ronik-analysis">')
        parts.append(f'    <p class="opp">💡 {escape(item["opportunity"])}</p>')
        if item.get("risk"):
            parts.append(f'    <p class="risk">⚠️ {escape(item["risk"])}</p>')
        if item.get("action"):
            parts.append(f'    <p class="action">🎯 {escape(item["action"])}</p>')
        parts.append("  </div>")
    else:
        # Standard format: summary + why
        summary = item.get("summary", "")
        if summary:
            parts.append(f'  <p class="item-summary">{escape(summary)}</p>')
        why = item.get("why", "")
        if why:
            parts.append(f'  <p class="item-why">→ {escape(why)}</p>')

    parts.append("</article>")
    return "\n".join(parts)


def render_section(section: dict) -> str:
    title = escape(section.get("title", ""))
    items = section.get("items", [])
    insight = section.get("insight", "")

    if not items:
        return ""

    parts: list[str] = ['<section class="section">']
    parts.append(f'  <h2 class="section-title">{title}</h2>')

    for item in items:
        parts.append(render_item(item))

    if insight:
        parts.append(
            f'  <aside class="section-insight">'
            f"💡 <strong>적용 아이디어</strong> — {escape(insight)}</aside>"
        )

    parts.append("</section>")
    return "\n".join(parts)


def render(data: dict, weather: dict | None = None) -> str:
    date_str = data.get("date", datetime.now().strftime("%Y-%m-%d"))
    kdate = korean_date(date_str)

    weather_html = ""
    if weather:
        weather_html = render_weather(weather)

    sections_html = "\n".join(
        render_section(s) for s in data.get("sections", []) if s.get("items")
    )

    highlight = data.get("highlight", "")
    highlight_html = ""
    if highlight:
        highlight_html = (
            '<div class="highlight">\n'
            '  <p class="highlight-label">★ 오늘의 핵심</p>\n'
            f'  <p class="highlight-text">{escape(highlight)}</p>\n'
            "</div>"
        )

    return f"""\
<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>밍밍 데일리 — {escape(date_str)}</title>
  <style>
{CSS}
  </style>
</head>
<body>
  <div class="newspaper">
    <header class="masthead">
      <div class="rule-top"></div>
      <div class="rule-top2"></div>
      <h1>밍밍 데일리</h1>
      <p class="subtitle">MINGMING DAILY</p>
      <p class="dateline">{escape(kdate)}</p>
      <div class="rule-bottom"></div>
    </header>

{weather_html}

{highlight_html}

    <main>
{sections_html}
    </main>

    <footer class="colophon">
      © {datetime.now().year} 밍밍 데일리 — AI 뉴스 브리핑
    </footer>
  </div>
</body>
</html>"""


def main() -> None:
    ap = argparse.ArgumentParser(description="Render news JSON → newspaper HTML")
    ap.add_argument("--input", help="JSON input file (default: stdin)")
    ap.add_argument("--weather", help="Weather JSON file from fetch_weather.py")
    ap.add_argument("--output", help="HTML output file (default: stdout)")
    args = ap.parse_args()

    if args.input:
        with open(args.input, "r", encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = json.load(sys.stdin)

    weather = None
    if args.weather:
        with open(args.weather, "r", encoding="utf-8") as f:
            weather = json.load(f)

    html = render(data, weather=weather)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"✅ {args.output}", file=sys.stderr)
    else:
        print(html)


if __name__ == "__main__":
    main()
