# News Brief Output Examples

## 1. news_brief.py JSON 출력

```json
[
  {
    "title": "[속보] 한은총재 \"금리점도표 도입, 임기전 마무리\"",
    "link": "https://www.yna.co.kr/view/AKR20260226102900002",
    "source": "yna.co.kr",
    "published": "2026-02-26 11:47 KST",
    "domain": "yna.co.kr",
    "tag": "경제",
    "description": "이창용 한은 총재가 점도표 도입 의지를 밝혔다.",
    "score": 7.62,
    "coverage": 2
  }
]
```

## 2. compose-newspaper.py 출력 (일부)

```json
{
  "date": "2026-02-26",
  "sections": [
    {
      "title": "🤖 AI·테크",
      "items": [
        {
          "headline": "Anthropic, Vercept 인수로 컴퓨터 사용 능력 강화",
          "url": "https://www.anthropic.com/news/acquires-vercept",
          "source": "anthropic.com",
          "tag": "Business",
          "published": "2026-02-25",
          "summary": "Claude의 컴퓨터 사용 벤치마크가 72.5%로 급등.",
          "why": "AI 에이전트의 GUI 조작 시대 본격화.",
          "origin_source": "Anthropic Blog"
        }
      ]
    },
    {
      "title": "💬 커뮤니티",
      "items": [
        {
          "headline": "LLM 기반 익명 사용자 신원 식별 연구",
          "url": "https://www.reddit.com/r/MachineLearning/...",
          "source": "reddit.com",
          "tag": "Community",
          "origin_source": "Reddit"
        }
      ]
    }
  ]
}
```

## 3. 최종 HTML

`render_newspaper.py` 출력. 섹션별 기사 카드 + 날씨 박스 + 옷차림 추천 포함.
파일명: `/tmp/mingming_daily_YYYY-MM-DD.html`
