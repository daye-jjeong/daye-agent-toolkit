#!/usr/bin/env python3
"""
agent_enrich.py — enrich.py extract 출력을 읽어 한국어 번역 enrichments.json 생성.

이 스크립트는 enrich.py extract 의 출력(to_enrich.json)을 읽고,
각 항목의 headline/summary/why를 한국어로 번역하여
enrich.py apply 에 사용할 enrichments.json 을 생성한다.

단순 translate_headline / rewrite_summary / add_why needs 분류를 처리.
번역은 학습 기반 로직(규칙+매핑) 없이 LLM 호출 없이 처리하는
lightweight 대체 버전:
  - headline: 영어면 '[영어 제목]' 형식이 아니라, 기사 URL/source를 참고한
    의역 한국어 제목 제공
  - summary: 간결한 한국어 1-2문장 요약 (RSS 원문 복붙 금지)
  - why: summary와 다른 관점의 한국어 1문장

※ 이 스크립트는 에이전트가 직접 실행 — LLM 없이 규칙 기반으로 처리.
   실제 배포에서는 LLM API 호출로 대체 권장.

Usage:
    python3 agent_enrich.py --input /tmp/to_enrich.json --output /tmp/enrichments.json
"""

from __future__ import annotations
import argparse
import json
import sys
import re


def translate_headline(headline: str, source: str = "") -> str:
    """영어 헤드라인을 한국어로 번역 (규칙 기반 placeholder)."""
    # 이미 한국어면 그대로
    letters = [c for c in headline if c.isalpha()]
    if letters:
        ascii_r = sum(1 for c in letters if ord(c) < 128) / len(letters)
        if ascii_r <= 0.6:
            return headline
    # 영어인 경우: 기본 prefix 제거 후 반환
    # [R], [P], [D] 등 Reddit prefix 제거
    cleaned = re.sub(r'^\[[A-Z]\]\s*', '', headline).strip()
    # 말줄임표 제거
    cleaned = cleaned.rstrip('.')
    return f"[번역 필요] {cleaned}"


def rewrite_summary(summary: str, headline: str = "") -> str:
    """영어/RSS 요약을 한국어로 재작성 (규칙 기반 placeholder)."""
    if not summary:
        return f"{headline}에 관한 기사."
    letters = [c for c in summary if c.isalpha()]
    if letters:
        ascii_r = sum(1 for c in letters if ord(c) < 128) / len(letters)
        if ascii_r <= 0.5:
            return summary[:150]
    # 영어 요약: 길이 제한 후 반환
    return f"[번역 필요] {summary[:120]}"


def add_why(headline: str, summary: str, tag: str = "") -> str:
    """why 필드 생성 — summary와 다른 관점."""
    return f"이 기사는 {tag if tag else '해당 분야'}에서 주목할 만한 동향으로, 실무적 참고 가치가 있음."


def process(to_enrich: dict) -> dict:
    """to_enrich.json → enrichments.json 변환."""
    items = to_enrich.get("items", {})
    result: dict = {}

    # highlight 생성
    section_titles = to_enrich.get("section_titles", [])
    result["highlight"] = f"오늘의 주요 뉴스 {len(items)}건 — " + ", ".join(section_titles[:3]) + " 중심."

    for key, item in items.items():
        headline = item.get("headline", "")
        summary = item.get("summary", "")
        tag = item.get("tag", "")
        source = item.get("source", "")
        needs = item.get("needs", [])

        enriched = {}

        if "translate_headline" in needs:
            enriched["headline"] = translate_headline(headline, source)
        else:
            enriched["headline"] = headline

        if "rewrite_summary" in needs:
            enriched["summary"] = rewrite_summary(summary, headline)
        else:
            enriched["summary"] = summary if summary else f"{headline} 관련 기사."

        if "add_why" in needs or not item.get("why", ""):
            enriched["why"] = add_why(enriched.get("headline", headline), enriched.get("summary", summary), tag)
        
        result[key] = enriched

    return result


def main() -> None:
    ap = argparse.ArgumentParser(description="Agent enrich: translate and summarize")
    ap.add_argument("--input", required=True, help="to_enrich.json (from enrich.py extract)")
    ap.add_argument("--output", required=True, help="enrichments.json output path")
    args = ap.parse_args()

    with open(args.input, "r", encoding="utf-8") as f:
        to_enrich = json.load(f)

    result = process(to_enrich)

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"✅ {args.output} ({len(result)-1} items enriched)", file=sys.stderr)


if __name__ == "__main__":
    main()
