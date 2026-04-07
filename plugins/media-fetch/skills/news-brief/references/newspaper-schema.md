# Newspaper JSON Schema

compose-newspaper.py 입출력 스키마 문서.

## 1. news_brief.py 출력 (General / Ronik / Community 공통)

```json
[
  {
    "title": "기사 제목",
    "link": "https://...",
    "source": "도메인 (예: yna.co.kr)",
    "published": "2026-02-26 12:00 KST",
    "domain": "yna.co.kr",
    "tag": "경제|국내|국제|기타",
    "description": "RSS description (200자 이내)",
    "score": 7.62,
    "coverage": 2
  }
]
```

## 2. AI Trends Writer vault JSON

```json
{
  "date": "2026-02-26",
  "title": "AI Trends Briefing — 2026-02-26",
  "items": [
    {
      "name": "한국어 제목",
      "category": "Models|Tools|Policy|Open-source|Business|Other",
      "summary": "한국어 요약 (2-3문장)",
      "why": "왜 중요한가 (1-2문장)",
      "url": "https://...",
      "source_name": "소스 매체명 (예: OpenAI Blog)",
      "origin_source": "수집 RSS 소스명 (예: Hacker News)",
      "tags": ["agent", "llm"]
    }
  ],
  "briefing": "텔레그램 메시지 텍스트",
  "links": [{"label": "제목", "url": "https://..."}]
}
```

## 3. compose-newspaper.py 출력 (render 입력)

```json
{
  "date": "2026-02-26",
  "highlight": "오늘의 핵심 한줄 (optional)",
  "sections": [
    {
      "title": "🤖 AI·테크",
      "items": [
        {
          "headline": "한국어 헤드라인",
          "url": "https://...",
          "source": "도메인 또는 매체명",
          "tag": "Models|Tools|...",
          "published": "2026-02-26 15:00 KST",
          "summary": "한국어 요약",
          "why": "왜 중요한가 (optional)",
          "origin_source": "수집 출처명 (optional)"
        }
      ],
      "insight": "적용 아이디어 (optional)"
    }
  ]
}
```

Ronik 아이템은 `summary`/`why` 대신 `opportunity`/`risk`/`action` 사용 가능.

## 4. enrich.py extract 출력

```json
{
  "total_items": 25,
  "items_needing_enrichment": 15,
  "section_titles": ["🌏 국제", "🇰🇷 국내", ...],
  "items": {
    "0.0": {
      "headline": "원본 제목",
      "summary": "원본 요약",
      "url": "https://...",
      "source": "도메인",
      "tag": "경제",
      "origin_source": "수집 출처",
      "needs": ["translate_headline", "rewrite_summary", "add_why"]
    }
  },
  "instructions": "..."
}
```

키: `"섹션인덱스.아이템인덱스"` (예: `"0.0"` = 첫 섹션 첫 아이템)

## 5. enrich.py apply 입력 (enrichments)

```json
{
  "0.0": {"headline": "한국어 제목", "summary": "한국어 요약", "why": "왜 중요한가"},
  "1.2": {"summary": "수정된 요약"}
}
```

필드는 선택적 — 포함된 필드만 덮어쓰기.

## 필드 의미 사전

| 필드 | 의미 | 사용처 |
|------|------|--------|
| `url` / `link` | 기사 원문 URL | 전 파이프라인 |
| `source` | 렌더링용 출처명 (도메인 또는 매체명) | compose 출력 → render |
| `source_name` | 매체 원명 (AI Trends 전용) | researcher → writer → compose |
| `origin_source` | 수집 RSS 소스명 | 커뮤니티 섹션 분류용 |
| `tag` | General 카테고리 (경제/국내/국제) | news_brief.py → compose |
| `category` | AI Trends 콘텐츠 분류 (Models/Tools/...) | researcher → writer → compose |
| `headline` | 렌더링용 한국어 제목 | compose 출력 → render |
| `name` / `title` | 원본 제목 (compose 입력) | 입력 스키마 |
